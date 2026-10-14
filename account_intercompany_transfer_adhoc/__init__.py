def uninstall_hook(env):
    """Put the menu back where account_intercompany_transfer defines it.

    Uninstalling this module leaves the values it wrote on the base module's
    menu in place; under ingadhoc's "Bank and Cash" menu (whose parent_id is
    ondelete='restrict'), that would also block uninstalling
    account_internal_transfer afterwards.
    """
    menu = env.ref("account_intercompany_transfer.menu_account_intercompany_transfer", raise_if_not_found=False)
    if menu:
        menu.write(
            {
                "parent_id": env.ref("account.account_transactions_menu").id,
                "sequence": 32,
            }
        )
