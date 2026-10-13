from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import IntercompanyTransferCommon


@tagged("post_install", "-at_install")
class TestBridgeAccount(IntercompanyTransferCommon):
    def test_account_of_another_company(self):
        with self.assertRaisesRegex(ValidationError, "does not belong to"):
            self.company_a.intercompany_transfer_account_id = self.bridge_b

    def test_archived_account(self):
        account = self._create_bridge_account(self.company_a, "119903")
        account.active = False
        with self.assertRaisesRegex(ValidationError, "is archived"):
            self.company_a.intercompany_transfer_account_id = account

    def test_account_types(self):
        for account_type in ("asset_cash", "asset_receivable", "liability_payable", "income", "equity"):
            account = self.env["account.account"].create(
                {
                    "name": f"Not a bridge {account_type}",
                    "code": f"9{len(account_type):02d}{account_type[:3].upper()}",
                    "account_type": account_type,
                    "reconcile": account_type in ("asset_receivable", "liability_payable"),
                    "company_ids": self.company_a.ids,
                }
            )
            with self.subTest(account_type=account_type), self.assertRaisesRegex(
                ValidationError, "current asset or a current liability"
            ):
                self.company_a.intercompany_transfer_account_id = account
        liability = self.env["account.account"].create(
            {
                "name": "Bridge liability",
                "code": "219901",
                "account_type": "liability_current",
                "company_ids": self.company_a.ids,
            }
        )
        self.company_a.intercompany_transfer_account_id = liability
        self.assertEqual(self.company_a.intercompany_transfer_account_id, liability)

    def test_outstanding_account_of_a_journal(self):
        outstanding = self.cash_a.outbound_payment_method_line_ids[:1].payment_account_id
        with self.assertRaisesRegex(ValidationError, "is the outstanding account"):
            self.company_a.intercompany_transfer_account_id = outstanding

    def test_settings_field(self):
        settings = self.env["res.config.settings"].with_company(self.company_a).create({})
        self.assertEqual(settings.intercompany_transfer_account_id, self.bridge_a)
        field = settings._fields["intercompany_transfer_account_id"]
        self.assertIn(("account_type", "in", ("asset_current", "liability_current")), field.domain)
        new_bridge = self._create_bridge_account(self.company_a, "119904")
        settings.intercompany_transfer_account_id = new_bridge
        settings.execute()
        self.assertEqual(self.company_a.intercompany_transfer_account_id, new_bridge)
        self.assertEqual(self.company_b.intercompany_transfer_account_id, self.bridge_b)
