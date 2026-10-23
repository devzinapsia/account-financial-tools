from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDateFormatDetection(AccountTestInvoicingCommon):
    """Bug fix: base_import's own date-format auto-detection tries every
    month-first pattern ('%m-%d-%Y') before its day-first equivalent
    ('%d-%m-%Y'). When a column's sample values are genuinely ambiguous
    (every day value is 12 or below), both match and the month-first one
    silently wins - every statement line gets its day and month swapped,
    with no error at all. Confirmed against a real BBVA export where every
    row fell in that exact window: 02-09-2026 (2 September) was imported
    as 9 February.
    """

    # Same values that triggered the real bug: every row's day component
    # (02 or 03) is also a valid month, so both orderings match every row.
    _AMBIGUOUS_DATES = [
        '03-09-2026', '02-09-2026', '02-09-2026', '02-09-2026',
        '02-09-2026', '02-09-2026', '02-09-2026',
    ]

    def _create_wizard(self):
        return self.env['base_import.import'].create({
            'res_model': 'account.bank.statement.line',
        })

    def test_ambiguous_date_prefers_day_first_for_bank_statement_import(self):
        wizard = self._create_wizard()
        options = {'bank_stmt_import': True}
        result = wizard._try_match_date_time(self._AMBIGUOUS_DATES, options)
        self.assertEqual(result, ['date', 'datetime'])
        self.assertEqual(options['date_format'], '%d-%m-%Y')

    def test_unambiguous_date_still_resolves_correctly(self):
        """A day value above 12 anywhere in the sample already rules out
        the month-first pattern on its own - the fix must not break this
        case, which was never actually buggy.
        """
        wizard = self._create_wizard()
        options = {'bank_stmt_import': True}
        dates = self._AMBIGUOUS_DATES + ['25-09-2026']
        result = wizard._try_match_date_time(dates, options)
        self.assertEqual(result, ['date', 'datetime'])
        self.assertEqual(options['date_format'], '%d-%m-%Y')

    def test_non_bank_statement_import_keeps_native_behavior(self):
        """The fix is scoped to bank_stmt_import only - a plain data
        import (contacts, products, generic model data) elsewhere in Odoo
        must keep behaving exactly as native base_import always has.
        """
        wizard = self._create_wizard()
        options = {}
        result = wizard._try_match_date_time(self._AMBIGUOUS_DATES, options)
        self.assertEqual(result, ['date', 'datetime'])
        self.assertEqual(options['date_format'], '%m-%d-%Y')

    def test_explicit_date_format_option_is_respected(self):
        """An explicit date_format (set by the user, or already resolved
        for an earlier date column of the same import) must win outright -
        the fix only kicks in while still genuinely auto-detecting.
        """
        wizard = self._create_wizard()
        options = {'bank_stmt_import': True, 'date_format': '%Y-%m-%d'}
        result = wizard._try_match_date_time(['2026-09-02', '2026-09-03'], options)
        self.assertEqual(result, ['date', 'datetime'])
        self.assertEqual(options['date_format'], '%Y-%m-%d')
