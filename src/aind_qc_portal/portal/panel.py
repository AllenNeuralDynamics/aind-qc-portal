"""Panels for the Portal app"""

import panel as pn
from panel.custom import PyComponent
from aind_qc_portal.layout import OUTER_STYLE


class Portal(PyComponent):

    def __init__(self):
        """Initialize the Portal app"""
        self.panel = pn.Column("here", styles=OUTER_STYLE)

    def __panel__(self):
        """Return the Panel representation of the Portal app"""
        return self.panel
