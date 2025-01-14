import panel as pn
import altair as alt
from datetime import datetime

from aind_qc_portal.projects.dataset import ProjectDataset
from aind_qc_portal.utils import df_timestamp_range, OUTER_STYLE, AIND_COLORS, range_unit_format


class AssetView():
    """Panel view of a single raw asset and its derived assets
    """

    def __init__(self, asset_id: str):
        pass


class ProjectView():
    """Panel view of an entire project's assets"""

    def __init__(self, project_name: str):
        """Create a new ProjectView object

        Parameters
        ----------
        project_name : str
            _description_
        """
        self.subject_filter = pn.widgets.MultiChoice(name="Subject filter")
        self.update(project_name)

    def update(self, new_project_name: str):
        print(f"Updating project view for {new_project_name}")
        self.dataset = ProjectDataset(new_project_name)
        self.project_name = new_project_name
        self.subject_filter.options = list(self.get_subjects())

    @property
    def has_data(self):
        return self.dataset.data is not None

    def get_subjects(self):
        if not self.has_data:
            return []

        return self.dataset.data["subject_id"].unique()

    def get_asset_count(self):
        if not self.has_data:
            return 0

        return len(self.dataset.data_filtered())

    def get_data_styled(self):
        if not self.has_data:
            return None

        return self.dataset.data_styled

    def history_panel(self):
        """Create a plot showing the history of this asset, showing how assets were derived from each other"""
        if not self.has_data:
            return pn.widgets.StaticText(
                value=f"No data found for project: {self.project_name}"
            )

        brush = alt.selection_interval(name='brush')

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(
            self.dataset.timestamps
        )

        chart = (
            alt.Chart(self.dataset.data_filtered())
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
                color=alt.condition(brush, alt.Color("subject_id:N"), alt.value('lightgray')),
                href=alt.Href("qc_link:N"),
            )
            .properties(width=900)
            .add_params(brush)
        )

        return pn.pane.Vega(chart, sizing_mode="stretch_width")

    def selection_history_panel(self, selection):
        """Create a plot showing the history of the selected assets"""
        if not self.has_data:
            return pn.widgets.StaticText(
                value=f"No data found for project: {self.project_name}"
            )

        data = self.dataset.data_filtered()

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(
            self.dataset.timestamps
        )

        if selection is None or selection == {}:
            data = data.head(0)
            self.subject_filter.value = []
        else:
            self.subject_filter.value = []
            if selection.get("subject_id") is not None:
                data = data[data["subject_id"].isin(selection["subject_id"])]
                self.subject_filter.value = selection["subject_id"]
            if selection.get("Date") is not None:
                min_range = datetime.fromtimestamp(selection["Date"][0] / 1000)
                max_range = datetime.fromtimestamp(selection["Date"][1] / 1000)
                (range_unit, format) = range_unit_format(
                    datetime.fromtimestamp(selection["Date"][1] / 1000) - datetime.fromtimestamp(selection["Date"][0] / 1000)
                )

        chart = (
            alt.Chart(data)
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
                href=alt.Href("qc_link:N"),
            )
            .properties(width=900)
        )

        return pn.pane.Vega(chart, sizing_mode="stretch_width")

    def panel(self) -> pn.Column:
        """Return panel object"""

        history_chart = self.history_panel()

        chart_pane = pn.Column(history_chart, pn.bind(self.selection_history_panel, history_chart.selection.param.brush), styles=OUTER_STYLE)

        df_pane = pn.pane.DataFrame(self.get_data_styled(), width=950, escape=False, index=False)

        def update_subject_filter(event):
            self.dataset.subject_filter = event.new
            df_pane.object = self.get_data_styled()

        self.subject_filter.param.watch(update_subject_filter, "value")

        df_col = pn.Column(self.subject_filter, df_pane, styles=OUTER_STYLE)

        col = pn.Column(chart_pane, df_col)

        return col
