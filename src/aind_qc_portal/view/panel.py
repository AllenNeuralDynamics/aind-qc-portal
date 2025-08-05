""" Panel objects for the View app """

import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.utils import OUTER_STYLE


class QCPanel(PyComponent):
    """Panel for displaying QC data"""

    record_name: param.String

    def __init__(self, record_name, data: ViewData):
        super().__init__()
        self.record_name = record_name
        self._data = data
        self._data.param.watch(self._update_panel_objects, "dirty")

        self._init_panel_objects()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.header = Header(data=self._data.record)

    def _update_panel_objects(self):
        """Update panel objects when data changes"""
        self.header.data = self._data.record

    def __panel__(self):
        """Create and return the Panel layout"""
        # Assuming that the QCPanel class has a method to create the panel layout

        header_submit_row = pn.Row(self.header, sizing_mode="stretch_width")
        content_row = pn.Row(
            self._data.dataframe,
            sizing_mode="stretch_width",
            styles=OUTER_STYLE,
        )

        return pn.Column(
            header_submit_row,
            content_row,
            sizing_mode="stretch_width",
        )


class Header(PyComponent):
    """Header for the QC view application"""

    data: param.Dict = param.Dict(default={})

    def __init__(self, data: dict):
        super().__init__()
        self.data = data

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.header_text = pn.pane.Markdown()

    @pn.depends("data")
    def __panel__(self):
        """Create and return the header layout"""

        header_md = f"""
## Quality control for {self.data["name"]}
"""
        header_text = pn.pane.Markdown(header_md)

        full_column = pn.Column(
            header_text,
            styles=OUTER_STYLE,
            sizing_mode="stretch_width"
        )
        return full_column
