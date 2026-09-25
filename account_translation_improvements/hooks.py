from odoo.tools.translate import TranslationImporter, get_po_paths

# account records renamed by data/account_overrides.xml, with their
# original (en_US) name in account.
OVERRIDDEN_NAMES = {
    "account.action_move_force_register_payment": "Pay",
    "account.menu_action_account_payments_receivable": "Payments",
    "account.action_account_payments": "Customer Payments",
    "account.menu_action_move_in_refund_type": "Refunds",
    "account.action_move_in_refund_type": "Refunds",
}


def force_translations(env, module_name, xmlids):
    """Write the translations of ``xmlids`` found in ``module_name``'s po
    files, replacing whatever translation the records already have.

    A regular module install/upgrade only loads a translation into a
    language that doesn't have one yet (unless Odoo runs with
    --i18n-overwrite, which odoo.sh doesn't), so a record owned by account
    keeps account's translation no matter what this module's po files say.
    """
    langs = [code for code, _name in env["res.lang"].get_installed() if code != "en_US"]
    importer = TranslationImporter(env.cr, verbose=False)
    for lang in langs:
        # Base language first (es, es_419, es_AR...), so the most specific wins
        for po_path in get_po_paths(module_name, lang):
            importer.load_file(po_path, lang, xmlids=set(xmlids))
    for fields in importer.model_translations.values():
        for field_name, records in fields.items():
            for xmlid, translations in records.items():
                record = env.ref(xmlid, raise_if_not_found=False)
                if record:
                    record.update_field_translations(field_name, translations)


def uninstall_hook(env):
    """Give the renamed account records back their original names, in
    en_US and in every installed language (from account's own po files)."""
    for xmlid, name in OVERRIDDEN_NAMES.items():
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.with_context(lang="en_US").name = name
    force_translations(env, "account", OVERRIDDEN_NAMES)
