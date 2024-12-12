from typing import Optional
import pandas as pd
import panel as pn
import altair as alt

from aind_qc_portal.projects.dataset import mapping, ProjectDataset
from aind_qc_portal.utils import df_timestamp_range, OUTER_STYLE, AIND_COLORS


class AssetView():
    """Panel view of a single raw asset and its derived assets
    """

    def __init__(self, asset_id: str):
        pass


class ProjectView():
    """Panel view of an entire project's assets"""

    def __init__(self, project_name: str):
        cls = mapping.get(project_name, ProjectDataset)
        self.dataset = cls(project_name=project_name)
        self.project_name = project_name

    @property
    def has_data(self):
        return self.dataset.data is not None

    def get_subjects(self):
        if not self.has_data:
            return []

        return self.dataset._df["subject_id"].unique()

    def get_data(self) -> Optional[pd.DataFrame]:
        if not self.has_data:
            return None

        return self.dataset.filtered_data()

    def get_data_styled(self):
        if not self.has_data:
            return None

        return self.dataset.data

    def history_panel(self):
        """Create a plot showing the history of this asset, showing how assets were derived from each other"""
        if not self.has_data:
            return pn.widgets.StaticText(
                value=f"No data found for project: {self.project_name}"
            )

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(
            self.dataset.timestamp_data
        )

        chart = (
            alt.Chart(self.get_data())
            .mark_bar()
            .encode(
                x=alt.X(
                    "Date:T",
                    title="Time",
                    scale=alt.Scale(domain=[min_range, max_range]),
                    axis=alt.Axis(format=format, tickCount=range_unit),
                ),
                y=alt.Y("subject_id:N", title="Subject ID"),
                tooltip=[
                    "subject_id",
                    "session_type",
                    "Date",
                ],
                color=alt.Color("subject_id:N"),
                href="qc_link:N",
            )
            .properties(width=900)
        )

        return pn.pane.Vega(chart, sizing_mode="stretch_width", styles=OUTER_STYLE)

    def panel(self) -> pn.Column:
        """Return panel object"""

        md = f"""
        <h1 style="color:{AIND_COLORS["dark_blue"]};">
            {self.project_name}
        </h1>
        <b>{len(self.dataset.filtered_data())}</b> data assets are associated with this project.
        """

        header = pn.pane.Markdown(md, width=1000, styles=OUTER_STYLE)

        chart_pane = self.history_panel()

        df_pane = pn.pane.DataFrame(self.get_data_styled(), width=950, escape=False, index=False)

        def update_subject_filter(event):
            self.dataset.subject_filter = event.new
            df_pane.object = self.get_data()

        subject_filter = pn.widgets.Select(name="Subject filter", options=[""] + list(self.get_subjects()))
        subject_filter.param.watch(update_subject_filter, "value")

        df_col = pn.Column(subject_filter, df_pane, styles=OUTER_STYLE)

        col = pn.Column(header, chart_pane, df_col)

        return col
