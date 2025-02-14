""" ProjectView class definition """

import panel as pn
import altair as alt
import pandas as pd
from datetime import datetime

from aind_qc_portal.projects.dataset import ProjectDataset
from aind_qc_portal.utils import (
    df_timestamp_range,
    OUTER_STYLE,
    range_unit_format,
)
from aind_qc_portal.projects.dataset import ALWAYS_COLUMNS


class DataframePanel:
    """Panel view of a group of assets"""

    def __init__(self, df: pd.DataFrame):
        self._panel = pn.widgets.Tabulator(
            pd.DataFrame(),
            width=950,
            show_index=False,
            disabled=True,
            formatters={
                "QC Status": {"type": "html"},
                "QC view": {"type": "html"},
                "S3 link": {"type": "html"},
            },
        )

    def update(self, df: pd.DataFrame):
        """Update the data in the panel"""
        self._panel.value = df

    def panel(self):
        return self._panel


class ProjectView:
    """Panel view of an entire project's assets"""

    def __init__(self, dataset: ProjectDataset):
        """Create a new ProjectView object"""
        self.project_name = ""
        self.dataset = dataset

        self.df_pane = DataframePanel(self.dataset.data_filtered())

        self.brush = alt.selection_interval(name="brush")
        self.history_chart = self.history_panel()
        if hasattr(self.history_chart, "selection"):
            self.selection_history_chart = pn.bind(
                self.selection_history_panel,
                self.history_chart.selection.param.brush,
            )
        else:
            self.selection_history_chart = pn.widgets.StaticText(value="")

    @property
    def has_data(self):
        """Check if the dataset has data"""
        return self.dataset.data is not None

    def get_asset_count(self):
        """Return the number of assets in the dataset"""
        if not self.has_data:
            return 0

        return len(self.dataset.data_filtered())

    def update_subject_selector(self, event):
        """Update the subject selector based on the brush selection"""
        if event.new.get("Subject ID") is not None:
            self.dataset.subject_selector.value = event.new["Subject ID"]
        else:
            self.dataset.subject_selector.value = []

    def history_panel(self):
        """Create a plot showing the history of this asset, showing how assets were derived from each other"""
        if not self.has_data:
            return pn.widgets.StaticText(value=f"No data found for project: {self.project_name}")

        data = self.dataset.data

        # Check that timestamp column has values
        if data["timestamp"].isnull().all():
            return pn.widgets.StaticText(
                value=(
                    "Data processing error: project is missing timestamp data in some assets."
                    "Please reach out to scientific computing for help repairing your metadata."
                )
            )

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(data[["timestamp"]])

        print(data.columns)

        chart = (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Acquisition Time:T",
                    title="Acquisition Time",
                    scale=alt.Scale(domain=[min_range, max_range]),
                    axis=alt.Axis(format=format, tickCount=range_unit),
                ),
                y=alt.Y("Subject ID:N", title="Subject ID"),
                tooltip=[
                    alt.Tooltip("Subject ID:N", title="Subject ID"),
                    alt.Tooltip("name:Q", title="Asset name"),
                    alt.Tooltip("session_type:Q", title="Session Type"),
                    alt.Tooltip("Acquisition Time:T", title="Acquisition Time"),
                ],
                color=alt.condition(
                    self.brush,
                    alt.Color("Subject ID:N"),
                    alt.value("lightgray"),
                ),
                href=alt.Href("qc_link:N"),
            )
            .properties(width=900)
            .add_params(self.brush)
        )

        chart_pane = pn.pane.Vega(chart, sizing_mode="stretch_width")
        chart_pane.selection.param.watch(self.update_subject_selector, "brush")

        return chart_pane

    def selection_history_panel(self, selection):
        """Create a plot showing the history of the selected assets"""
        if not self.has_data:
            return pn.widgets.StaticText(value=f"No data found for project: {self.project_name}")

        data = self.dataset.data_filtered()

        if data.empty:
            return pn.widgets.StaticText(value="No data found for the selected filters")

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(self.dataset.timestamps)

        if selection is None or selection == {}:
            data = data.head(0)
        else:
            if selection.get("Subject ID") is not None:
                data = data[data["Subject ID"].isin(selection["Subject ID"])]
            if selection.get("Acquisition Time") is not None:
                min_range = datetime.fromtimestamp(selection["Acquisition Time"][0] / 1000)
                max_range = datetime.fromtimestamp(selection["Acquisition Time"][1] / 1000)
                (range_unit, format) = range_unit_format(
                    datetime.fromtimestamp(selection["Acquisition Time"][1] / 1000)
                    - datetime.fromtimestamp(selection["Acquisition Time"][0] / 1000)
                )

        chart = (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Acquisition Time:T",
                    title="Time",
                    scale=alt.Scale(domain=[min_range, max_range]),
                    axis=alt.Axis(format=format, tickCount=range_unit),
                ),
                y=alt.Y("Subject ID:N", title="Subject ID"),
                tooltip=[
                    alt.Tooltip("Subject ID:N", title="Subject ID"),
                    alt.Tooltip("name:Q", title="Asset name"),
                    alt.Tooltip("Type:Q", title="Session Type"),
                    alt.Tooltip("Acquisition Time:T", title="Acquisition Time"),
                ],
                color=alt.Color("Subject ID:N"),
                href=alt.Href("qc_link:N"),
            )
            .properties(width=900)
        )

        return pn.pane.Vega(chart, sizing_mode="stretch_width")

    def _panel(
        self,
        subject_filter,
        derived_filter,
        columns_filter,
        type_filter,
        status_filter,
    ) -> pn.Column:
        """Helper function to construct the settings section of the panel object"""

        self.dataset.subject_filter = subject_filter
        self.dataset.derived_filter = derived_filter
        self.dataset.columns_filter = ALWAYS_COLUMNS + columns_filter
        self.dataset.type_filter = type_filter
        self.dataset.status_filter = status_filter

        self.df_pane.update(self.dataset.data_filtered())

        col = pn.Column(self.selection_history_chart, self.df_pane.panel())

        return col

    def panel(self):
        """Return the panel object"""

        return pn.Column(
            self.history_chart,
            pn.bind(
                self._panel,
                subject_filter=self.dataset.subject_selector,
                derived_filter=self.dataset.derived_selector,
                columns_filter=self.dataset.columns_selector,
                type_filter=self.dataset.type_selector,
                status_filter=self.dataset.status_selector,
            ),
            styles=OUTER_STYLE,
        )
