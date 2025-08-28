"""Portal main entrypoint"""

import panel as pn
from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.panel import Portal
from aind_qc_portal.utils import format_css_background

pn.extension('jsoneditor', notifications=True)

format_css_background()

database = Database()
portal = Portal(database=database)


portal.__panel__().servable(title="QC Portal")
