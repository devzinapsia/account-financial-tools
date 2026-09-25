from odoo.addons.account_translation_improvements.hooks import force_translations

# account_batch_payment records renamed by
# data/account_batch_payment_overrides.xml, with their original (en_US) name.
OVERRIDDEN_NAMES = {
    "account_batch_payment.menu_batch_payment_sales": "Batch Payments",
    "account_batch_payment.action_batch_payment_in": "Customer Batch Payments",
}


def uninstall_hook(env):
    """Give the renamed records back their original names, in en_US and in
    every installed language (from account_batch_payment's own po files)."""
    for xmlid, name in OVERRIDDEN_NAMES.items():
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.with_context(lang="en_US").name = name
    force_translations(env, "account_batch_payment", OVERRIDDEN_NAMES)
