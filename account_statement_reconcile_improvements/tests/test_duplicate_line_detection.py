import json

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDuplicateLineDetection(AccountTestInvoicingCommon):
    """3.4: importing a file that overlaps with an already-imported statement
    must not crash, and must report the skipped duplicate rows.

    Regression test for two real bugs found by hand-testing in production:
    1. The duplicate count was stashed on `self` inside _parse_import_data,
       but account_bank_statement_import_csv's execute_import() calls
       super() on self.with_context(...), a *different* recordset than the
       one execute_import() itself runs on - crashed server-side with
       AttributeError instead of just being silently wrong.
    2. Once fixed server-side, the notice was added to res['messages'] -
       base_import's own blocking-error channel, where every entry is
       expected to carry a 'rows': {'from', 'to'} pair - which crashed the
       JS client instead (_groupErrorsByField reading `.rows.to` off an
       entry with no `rows`).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']
        # An existing line that the test import below will collide with:
        # same date, no partner, same amount.
        cls.env['account.bank.statement'].create({
            'name': 'Existing Statement',
            'journal_id': cls.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': '2026-01-05',
                'payment_ref': 'Already imported',
                'amount': 100.0,
                'journal_id': cls.bank_journal.id,
            })],
        })

    def _create_wizard(self, csv_content):
        return self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': csv_content.encode(),
            'file_name': 'test_import.csv',
            'file_type': 'text/csv',
        })

    def test_dryrun_import_with_a_duplicate_row_does_not_crash(self):
        csv_content = "Fecha,Importe\n2026-01-05,100.0\n2026-01-06,250.0\n"
        wizard = self._create_wizard(csv_content)
        options = {
            'has_headers': True,
            'bank_stmt_import': True,
            'quoting': '"',
            'separator': ',',
            'encoding': 'utf-8',
        }
        result = wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options=options,
            dryrun=True,
        )

        # Must not be reported through res['messages']: that channel is
        # base_import's own blocking-error pipeline and expects every entry
        # to carry a 'rows': {'from', 'to'} pair - putting a plain notice
        # there is what crashed the JS client (_groupErrorsByField reading
        # `.rows.to` off an entry that has no `rows`).
        messages = result.get('messages') or []
        self.assertFalse(
            any(m.get('type') == 'error' for m in messages),
            f"Unexpected error(s) in dryrun import result: {messages}",
        )
        for message in messages:
            self.assertIn('rows', message, f"message dict missing 'rows', would crash the JS client: {message}")

        # The duplicate-skip notice must instead go out as a non-blocking
        # bus notification (self.env.user._bus_send('simple_notification', ...)).
        # _bus_send() only queues the row in cr.precommit (flushed to the
        # bus.bus table on commit, which TransactionCase tests never do) -
        # so it's checked directly on that in-memory queue instead of the
        # bus.bus table.
        queued_bus_values = self.env.cr.precommit.data.get("bus.bus.values", [])
        self.assertTrue(
            any('duplicate' in value['message'].lower() for value in queued_bus_values),
            f"Expected a queued bus 'simple_notification' about the skipped duplicate row, got: {queued_bus_values}",
        )
        # The notice must be sticky (won't auto-dismiss) - a plain "N rows
        # skipped" toast that vanishes in a couple seconds isn't actionable.
        # It's deliberately kept short (just the count), not an itemized
        # per-row list: a real case with 42 duplicate rows made that
        # unreadable crammed into a toast - full per-row detail is instead
        # posted to the resulting statement's chatter on the real import.
        self.assertTrue(
            any(
                json.loads(value['message'])['payload'].get('sticky')
                for value in queued_bus_values
            ),
            f"Expected a sticky notification about the skipped duplicate row, got: {queued_bus_values}",
        )

    def test_duplicate_is_caught_even_when_partner_is_not_self_resolved(self):
        """Regression test for the real bug reported after deploy: an
        existing line whose partner was set some other way (a plain
        'partner_id' mapping, or a statement imported before this module
        existed at all) was never flagged as a duplicate, because the
        dedup check only trusted a partner value it resolved itself and
        otherwise assumed partner_id=False - silently missing real
        duplicates instead of catching them. It must now fall back to
        matching on date+amount alone when partner isn't self-resolved.
        """
        self.env['account.bank.statement'].create({
            'name': 'Existing Statement With Partner',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': '2026-02-10',
                'payment_ref': 'Already imported, with partner',
                'partner_id': self.partner_a.id,
                'amount': 500.0,
                'journal_id': self.bank_journal.id,
            })],
        })
        csv_content = "Fecha,Importe\n2026-02-10,500.0\n"
        wizard = self._create_wizard(csv_content)
        result = wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options={
                'has_headers': True,
                'bank_stmt_import': True,
                'quoting': '"',
                'separator': ',',
                'encoding': 'utf-8',
            },
            dryrun=True,
        )
        self.assertFalse(result.get('ids'), "The duplicate row should have been skipped, not imported")

    def test_real_import_with_only_duplicate_rows_leaves_no_empty_statement(self):
        """account_bank_statement_import_csv unconditionally creates a new
        account.bank.statement after import, even with an empty line_ids -
        e.g. when every row was filtered out as a probable duplicate. A
        real (non-dryrun) import where every row is a duplicate must not
        leave that useless, zero-line statement behind.
        """
        statement_count_before = self.env['account.bank.statement'].search_count([
            ('journal_id', '=', self.bank_journal.id),
        ])
        csv_content = "Fecha,Importe\n2026-01-05,100.0\n"
        wizard = self._create_wizard(csv_content)
        result = wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options={
                'has_headers': True,
                'bank_stmt_import': True,
                'quoting': '"',
                'separator': ',',
                'encoding': 'utf-8',
            },
            dryrun=False,
        )
        self.assertFalse(result.get('ids'), "The duplicate row should have been skipped, not imported")
        statement_count_after = self.env['account.bank.statement'].search_count([
            ('journal_id', '=', self.bank_journal.id),
        ])
        self.assertEqual(
            statement_count_before, statement_count_after,
            "No new (empty) statement should remain when every row was a probable duplicate",
        )
        # Without this, clicking "Importar" directly (skipping "Probar") on
        # an all-duplicates file looked like it silently did nothing.
        queued_bus_values = self.env.cr.precommit.data.get("bus.bus.values", [])
        self.assertTrue(
            any(
                json.loads(value['message'])['payload'].get('sticky')
                and 'nothing was imported' in json.loads(value['message'])['payload'].get('message', '').lower()
                for value in queued_bus_values
            ),
            f"Expected a sticky 'nothing imported' notification, got: {queued_bus_values}",
        )

    def test_real_import_with_mixed_rows_posts_rejected_rows_to_chatter(self):
        """When a real (non-dryrun) import produces at least one imported
        line, any rejected probable-duplicate rows must be listed on the
        resulting statement's chatter (date, amount, description, contact)
        - not just the transient toast, which the user might miss and which
        only fires on "Probar" anyway.
        """
        csv_content = "Fecha,Etiqueta,Importe\n2026-01-05,Duplicate row,100.0\n2026-01-06,New row,250.0\n"
        wizard = self._create_wizard(csv_content)
        result = wizard.execute_import(
            fields=['date', 'payment_ref', 'amount'],
            columns=['Fecha', 'Etiqueta', 'Importe'],
            options={
                'has_headers': True,
                'bank_stmt_import': True,
                'quoting': '"',
                'separator': ',',
                'encoding': 'utf-8',
            },
            dryrun=False,
        )
        self.assertEqual(len(result.get('ids') or []), 1, "Only the new row should have been imported")

        imported_line = self.env['account.bank.statement.line'].browse(result['ids'])
        statement = imported_line.statement_id
        messages = statement.message_ids
        self.assertTrue(messages, "Expected a chatter message on the resulting statement")
        table_message = next((m for m in messages if 'were not imported' in (m.body or '')), None)
        self.assertIsNotNone(table_message, f"Expected a chatter message listing the rejected row, got: {[m.body for m in messages]}")
        self.assertIn('2026-01-05', table_message.body)
        self.assertIn('100.0', table_message.body)
        # The rejected *incoming* row's own description ("Duplicate row")
        # must show, not the pre-existing line's ("Already imported") -
        # they're two different records with the same date/amount.
        self.assertIn('Duplicate row', table_message.body)
        self.assertNotIn('Already imported', table_message.body)
        # Regression test: "".join() on the per-row Markup chunks silently
        # degraded the result back to a plain str, which then got
        # HTML-escaped all over again by the outer Markup(...).format() -
        # the <tr><td> tags showed up as literal escaped text in the
        # chatter instead of an actual rendered table.
        self.assertIn('<tr><td>2026-01-05</td>', table_message.body)
        self.assertNotIn('&lt;tr&gt;', table_message.body)
