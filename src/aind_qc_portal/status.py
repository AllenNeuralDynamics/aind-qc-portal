"""Status main entrypoint"""
import panel as pn

from aind_qc_portal.status_contents.panel import StatusPanel

pn.extension()
status_panel = StatusPanel()
status_panel.panel.servable(title="QC Portal Status", location="/status")
