"""Portal main entrypoint"""

import panel as pn
from aind_qc_portal.portal_contents.database import Database
from aind_qc_portal.portal_contents.panel import Portal
from aind_qc_portal.utils import format_css_background

pn.extension(
    "jsoneditor",
    "modal",
    "tabulator",
    disconnect_notification="Connection lost, please reload the page!",
    notifications=True,
)

format_css_background()

database = Database()
portal = Portal(database=database)

portal.__panel__().servable(title="QC Portal")
