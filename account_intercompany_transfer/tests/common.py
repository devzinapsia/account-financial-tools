from odoo import Command, fields

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class IntercompanyTransferCommon(AccountTestInvoicingCommon):
    """Companies A and B have a bridge account, company C doesn't."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Errors and chatter are rendered in the acting user's language;
        # pin it so assertions don't depend on the loaded languages.
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"

        # Records created by the parent setup keep its environment (and its
        # language): bind them to the pinned one.
        cls.company_data = {key: value.with_env(cls.env) for key, value in cls.company_data.items()}
        cls.company_a = cls.company_data["company"]
        cls.company_b_data = cls.setup_other_company(name="Company B")
        cls.company_b = cls.company_b_data["company"]
        cls.company_c_data = cls.setup_other_company(name="Company C")
        cls.company_c = cls.company_c_data["company"]
        # Branch-free, same currency for the three companies.
        cls.currency = cls.company_a.currency_id
        (cls.company_b | cls.company_c).currency_id = cls.currency

        cls.bridge_a = cls._create_bridge_account(cls.company_a, "119901")
        cls.bridge_b = cls._create_bridge_account(cls.company_b, "119902")
        cls.company_a.intercompany_transfer_account_id = cls.bridge_a
        cls.company_b.intercompany_transfer_account_id = cls.bridge_b

        cls.cash_a = cls._setup_journal(cls.company_data["default_journal_cash"])
        cls.bank_a = cls._setup_journal(cls.company_data["default_journal_bank"])
        cls.cash_b = cls._setup_journal(cls.company_b_data["default_journal_cash"])
        cls.bank_b = cls._setup_journal(cls.company_b_data["default_journal_bank"])
        cls.cash_c = cls._setup_journal(cls.company_c_data["default_journal_cash"])

        cls.group_transfer = cls.env.ref("account_intercompany_transfer.group_intercompany_transfer_user")
        cls.group_invoice = cls.env.ref("account.group_account_invoice")
        # The test environment's own user (not the superuser) reads the
        # transfers in assertions.
        cls.env.user.group_ids |= cls.group_transfer
        cls.user_transfer = cls._create_user(
            "ict_user", cls.company_a | cls.company_b | cls.company_c, cls.group_transfer | cls.group_invoice
        )
        cls.user_no_group = cls._create_user("ict_no_group", cls.company_a | cls.company_b, cls.group_invoice)
        cls.user_only_a = cls._create_user("ict_only_a", cls.company_a, cls.group_transfer | cls.group_invoice)
        cls.today = fields.Date.today()

    @classmethod
    def _create_bridge_account(cls, company, code):
        return cls.env["account.account"].create(
            {
                "name": "Intercompany bridge",
                "code": code,
                "account_type": "asset_current",
                "company_ids": [Command.set(company.ids)],
            }
        )

    @classmethod
    def _setup_journal(cls, journal):
        """Give the manual payment methods of a journal the company's
        outstanding receipts/payments accounts, as an accountant would.
        """
        chart = cls.env["account.chart.template"].with_company(journal.company_id)
        journal.inbound_payment_method_line_ids.payment_account_id = chart.ref(
            "account_journal_payment_debit_account_id"
        )
        journal.outbound_payment_method_line_ids.payment_account_id = chart.ref(
            "account_journal_payment_credit_account_id"
        )
        return journal

    @classmethod
    def _create_user(cls, login, companies, groups):
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": login,
                    "login": login,
                    "lang": "en_US",
                    "email": f"{login}@test.example.com",
                    "company_id": companies[0].id,
                    "company_ids": [Command.set(companies.ids)],
                    "group_ids": [Command.set(groups.ids)],
                }
            )
        )

    def _as_user(self, model, user=None, ticked=None):
        """Model as a user with only some companies ticked in the switcher
        (only their first company by default, the usual case).
        """
        user = user or self.user_transfer
        ticked = ticked or user.company_id
        return self.env[model].with_user(user).with_context(allowed_company_ids=ticked.ids)

    def _transfer(self, amount=10000.0, origin=None, destination=None, user=None, date=None, memo="Funding"):
        transfer = self._as_user("account.intercompany.transfer", user)._create_transfer(
            origin or self.cash_a,
            destination or self.cash_b,
            amount,
            date or self.today,
            memo,
        )
        # Back to the superuser: assertions read both companies' records.
        return self.env["account.intercompany.transfer"].browse(transfer.id)

    def _reconcile_with_statement(self, payment):
        """Match the outstanding line of a payment with a bank statement
        line, as the bank reconciliation does: the statement line's suspense
        item moves to the outstanding account and both get reconciled.
        """
        amount = payment.amount if payment.payment_type == "inbound" else -payment.amount
        st_line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": payment.journal_id.id,
                "amount": amount,
                "date": payment.date,
                "payment_ref": f"Statement {payment.name}",
            }
        )
        _liquidity, suspense, _other = st_line._seek_for_lines()
        suspense.account_id = payment.outstanding_account_id
        payment_line = payment.move_id.line_ids.filtered(lambda line: line.account_id == payment.outstanding_account_id)
        (suspense | payment_line).reconcile()
        return st_line
