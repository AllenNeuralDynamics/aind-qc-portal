""" Panel objects for the View app """

from pydantic import BaseModel
import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.utils import OUTER_STYLE
from aind_qc_portal.view.panel.header import Header


class QCPanel(PyComponent):
    """Panel for displaying QC data"""

    record_name: param.String

    def __init__(self, record_name, data: ViewData):
        super().__init__()
        self.record_name = record_name
        self._data = data
        self._data.param.watch(self._update_record_dependencies, "record")
        self._data.param.watch(self._update_status_dependencies, "status")

        self._init_panel_objects()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.header = Header(data=self._data.record, status=self._data.status)
        self.groups = Groups(default_grouping=self._data.default_grouping, grouping_options=self._data.grouping_options)

    def _update_record_dependencies(self):
        """Update panel objects when data changes"""
        self.header.data = self._data.record

    def _update_status_dependencies(self):
        """Update panel objects when status changes"""
        self.header.status = self._data.status

    def __panel__(self):
        """Create and return the Panel layout"""
        # Assuming that the QCPanel class has a method to create the panel layout

        header_submit_row = pn.Row(self.header, sizing_mode="stretch_width")
        metrics_col = pn.Column(self._data.dataframe, sizing_mode="stretch_width", styles=OUTER_STYLE)
        content_row = pn.Row(
            self.groups,
            metrics_col,
            sizing_mode="stretch_width",
        )

        return pn.Column(
            header_submit_row,
            content_row,
            sizing_mode="stretch_width",
        )


class GroupMetricData(BaseModel):
    """Data model for a single metric in the groups view"""

    name: str
    tags: list[str]
    modalities: list[str]


class Groups(PyComponent):
    """Panel for displaying the metric groups and their status"""

    groups = param.List(default=[])
    grouping_options = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        super().__init__()

        self.groups = default_grouping
        self.grouping_options = grouping_options

    def __panel__(self):
        """Create and return the settings panel"""
        return pn.Column(
            pn.widgets.MultiChoice(
                name="Group metrics by these tags/modalities:",
                options=self.grouping_options,
                value=self.groups,
            ),
            styles=OUTER_STYLE,
            width=400,
        )
