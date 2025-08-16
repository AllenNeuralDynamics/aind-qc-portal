""" Main Panel object for the view app

This only builds the columns/rows of the main layout. It shouldn't use the OUTER_STYLE styling anywhere.
"""

import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.view.panels.header import Header
from aind_qc_portal.view.panels.settings import Settings
from aind_qc_portal.view.panels.metrics import Metrics


class QCPanel(PyComponent):
    """Panel for displaying QC data"""

    record_name: param.String

    def __init__(self, record_name, data: ViewData):
        super().__init__()
        self.record_name = record_name
        self._data = data

        self._init_panel_objects()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.settings = Settings(default_grouping=self._data.default_grouping, grouping_options=self._data.grouping_options)
        # Other panels have a dependency on settings
        self.header = Header(data=self._data.record, status=self._data.status, settings=self.settings)
        self.metrics = Metrics(data=self._data, settings=self.settings, callback=self._data.submit_change)

    def __panel__(self):
        """Create and return the Panel layout"""
        # Assuming that the QCPanel class has a method to create the panel layout

        header_submit_row = pn.Row(self.header, sizing_mode="stretch_width")
        content_row = pn.Row(
            self.metrics,
            sizing_mode="stretch_width",
        )

        return pn.Column(
            header_submit_row,
            content_row,
            sizing_mode="stretch_width",
        )
