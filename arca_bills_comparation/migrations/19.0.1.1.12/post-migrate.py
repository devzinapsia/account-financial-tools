from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Make files/folders created before 19.0.1.1.12 readable by every internal user.

    They were created with Documents' default internal access ("None"), so
    only the uploader could read a run's file; anyone else got an access
    error opening or reprocessing that run.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    documents = env["arca.bill.comparison.batch"].with_context(active_test=False).search(
        [("source_document_id", "!=", False)]
    ).source_document_id
    folder = env["arca.bill.comparison.batch"]._get_or_create_arca_documents_folder()
    to_fix = (documents | folder | folder.folder_id).filtered(lambda d: d.access_internal == "none")
    to_fix.write({"access_internal": "view"})
