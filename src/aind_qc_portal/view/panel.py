""" Panel objects for the View app """

from typing import Callable
import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.utils import OUTER_STYLE, qc_status_color_css
from aind_qc_portal.view.panel_metrics import MetricMedia, MetricValue

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
        multichoice = pn.widgets.MultiChoice(
            name="Group metrics by these tags/modalities:",
            options=self.grouping_options,
            value=self.group_by,
        )

        # Bind the widget value to the parameter
        multichoice.link(self, value='group_by')

        return pn.Column(multichoice)


class MetricTab(PyComponent):
    """Panel for displaying a single MetricMedia panel and its associated MetricValue panels"""


class Metrics(PyComponent):
    """Panel for displaying the metrics"""

    def __init__(self, data: ViewData, settings: Settings, callback: Callable):
        super().__init__()
        self._init_panel_objects()
        self._construct_metrics(data)

        self.settings = settings
        self.settings.param.watch(self._populate_metrics, 'group_by')

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.tabs = pn.Tabs()

    def _construct_metrics(self, data: ViewData):
        """Build all MetricValue/MetricMedia panels"""

    def _populate_metrics(self, data: ViewData):
        """Populate the metrics tabs with data"""
        # Use the group_by field

    def __panel__(self):
        """Create and return the metrics panel"""

        return self.tabs


class Header(PyComponent):
    """Header for the QC view application"""

    data: param.Dict = param.Dict(default={})
    status: param.DataFrame = param.DataFrame(default=pd.DataFrame())

    def __init__(self, data: dict, status: dict, settings: Settings):
        super().__init__()
        self._init_panel_objects()

        self.data = data
        self.status = status
        self.settings = settings

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
## QC for {self.data["name"]}
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
            self.settings,
            styles=OUTER_STYLE,
            sizing_mode="stretch_width"
        )
        return full_column
