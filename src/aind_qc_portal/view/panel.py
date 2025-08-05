""" Panel objects for the View app """

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.utils import OUTER_STYLE, qc_status_color_css


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
        self.settings = Settings(default_grouping=self._data.default_grouping, grouping_options=self._data.grouping_options)

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
        settings_row = pn.Row(self.settings, sizing_mode="stretch_width")
        content_row = pn.Row(
            self._data.dataframe,
            sizing_mode="stretch_width",
            styles=OUTER_STYLE,
        )

        return pn.Column(
            header_submit_row,
            settings_row,
            content_row,
            sizing_mode="stretch_width",
        )


class Groups(PyComponent):
    """Panel for displaying the metric groups and their status"""


class Settings(PyComponent):
    """Settings for the QC view application"""

    group_by = param.List(default=[])
    grouping_options = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        super().__init__()

        self.group_by = default_grouping
        self.grouping_options = grouping_options

    def __panel__(self):
        """Create and return the settings panel"""
        return pn.Column(
            pn.widgets.MultiChoice(
                name="Group metrics by these tags/modalities:",
                options=self.grouping_options,
                value=self.group_by,
            ),
            styles=OUTER_STYLE,
            sizing_mode="stretch_width",
        )


class Header(PyComponent):
    """Header for the QC view application"""

    data: param.Dict = param.Dict(default={})
    status: param.DataFrame = param.DataFrame(default=pd.DataFrame())

    def __init__(self, data: dict, status: dict):
        super().__init__()
        self._init_panel_objects()

        self.data = data
        self.status = status

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.header_text = pn.pane.Markdown()
        self.status_table = pn.pane.DataFrame(
            index=False,
            escape=False,
        )

    @pn.depends("data", watch=True)
    def _header_panel(self):
        header_md = f"""
## Quality control for {self.data["name"]}
"""
        self.header_text.object = header_md

        return self.header_text

    @pn.depends("status", watch=True)
    def _status_panel(self):
        """Create a table to display the status of the QC metrics"""
        if not self.status.empty:
            # Get column names excluding the first column
            columns_to_style = self.status.columns[1:]

            styled_df = self.status.style.apply(
                lambda x: [qc_status_color_css(val) if isinstance(val, str) else "" for val in x],
                subset=columns_to_style,
                axis=0
            ).hide(axis="index").set_table_styles([
                {'selector': 'table', 'props': [('border-collapse', 'collapse')]},
                {'selector': 'th, td', 'props': [('border', '1px solid #ddd'), ('padding', '8px')]},
            ])

            self.status_table.object = styled_df
        else:
            self.status_table.object = self.status

        return self.status_table

    def __panel__(self):
        """Create and return the header layout"""

        full_column = pn.Column(
            self._header_panel(),
            self._status_panel(),
            styles=OUTER_STYLE,
            sizing_mode="stretch_width"
        )
        return full_column
