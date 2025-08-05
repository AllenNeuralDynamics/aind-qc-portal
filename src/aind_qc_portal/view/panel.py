""" Panel objects for the View app """

import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view.database import ViewData


class QCPanel(PyComponent):
    """Panel for displaying QC data"""

    data: param.Parameterized

    def __init__(self, name, data: ViewData):
        self.id = name
        self.data = data

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

    def __panel__(self):
        """Create and return the Panel layout"""
        # Assuming that the QCPanel class has a method to create the panel layout

        return pn.Column(
            pn.pane.Markdown(f"## QC Data for ID: {self.id}"),
            pn.pane.DataFrame(self.data.param.dataframe, width=800),
            sizing_mode="stretch_width"
        )


class Header(PyComponent):
    """Header for the QC view application"""

    data: param.Dict = param.Dict(default={})

    def __init__(self, title: str = "AIND QC - View"):
        self.title = title

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

    @pn.depends("data")
    def __panel__(self):
        """Create and return the header layout"""
        return pn.pane.Markdown(f"# {self.title}", style={"text-align": "center"}, sizing_mode="stretch_width")
