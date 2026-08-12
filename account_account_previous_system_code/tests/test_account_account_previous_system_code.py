from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountAccountPreviousSystemCode(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.account_model = cls.env["account.account"]

    def _create_account(self, code, **kwargs):
        vals = {
            "name": f"Test account {code}",
            "code": code,
            "account_type": "asset_current",
        }
        vals.update(kwargs)
        return self.account_model.create(vals)

    def test_create_account_with_empty_code_does_not_raise(self):
        """An account without a previous system code can be created."""
        account = self._create_account("PSC001")
        self.assertFalse(account.previous_system_account_code)

    def test_duplicate_code_raises_on_create(self):
        """Two accounts sharing a company cannot use the same non-empty
        previous system account code."""
        self._create_account(
            "PSC010", previous_system_account_code="OLD-100"
        )
        with self.assertRaisesRegex(ValidationError, "OLD-100"):
            self._create_account(
                "PSC011", previous_system_account_code="OLD-100"
            )

    def test_multiple_empty_codes_do_not_raise(self):
        """Several accounts can be created at once with an empty previous
        system account code without being treated as duplicates of each
        other."""
        accounts = self.account_model.create(
            [
                {
                    "name": f"Test account PSC02{i}",
                    "code": f"PSC02{i}",
                    "account_type": "asset_current",
                }
                for i in range(3)
            ]
        )
        self.assertEqual(len(accounts), 3)
        self.assertFalse(
            any(accounts.mapped("previous_system_account_code"))
        )

    def test_write_duplicate_code_raises(self):
        """Writing a previous system account code already used by another
        account raises ValidationError."""
        self._create_account(
            "PSC030", previous_system_account_code="OLD-200"
        )
        other = self._create_account("PSC031")
        with self.assertRaisesRegex(ValidationError, "OLD-200"):
            other.previous_system_account_code = "OLD-200"

    def test_write_own_code_unchanged_does_not_raise(self):
        """Re-writing the same value on the same account is not a
        duplicate of itself."""
        account = self._create_account(
            "PSC040", previous_system_account_code="OLD-300"
        )
        account.previous_system_account_code = "OLD-300"
        self.assertEqual(account.previous_system_account_code, "OLD-300")

    def test_search_by_previous_system_account_code(self):
        """account.account records can be searched by
        previous_system_account_code."""
        account = self._create_account(
            "PSC050", previous_system_account_code="OLD-400"
        )
        result = self.account_model.search(
            [("previous_system_account_code", "=", "OLD-400")]
        )
        self.assertIn(account, result)

        result_none = self.account_model.search(
            [("previous_system_account_code", "=", "OLD-999")]
        )
        self.assertNotIn(account, result_none)
