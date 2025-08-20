"""Panels for the Portal app"""

import panel as pn
from panel.custom import PyComponent
from aind_qc_portal.layout import OUTER_STYLE


class Portal(PyComponent):

    def __init__(self):
        """Initialize the Portal app"""
        self._init_panel_components()

    def _init_panel_components(self):
        """Initialize the components of the Portal app"""

        self.project_selector = pn.widgets.MultiChoice(
            name="data_description.project_name",
            options=[],
        )

        self.main_col = pn.Column(
            self.project_selector,
            styles=OUTER_STYLE
        )

        self.panel = pn.Row(pn.HSpacer(), self.main_col, pn.HSpacer())

    def __panel__(self):
        """Return the Panel representation of the Portal app"""
        return self.panel
