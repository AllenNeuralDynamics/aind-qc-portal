# Minimal Panel serve entrypoint for status page
import panel as pn
from aind_qc_portal.view_contents.status_panel import status_panel

pn.extension()
status_panel.panel.servable()
