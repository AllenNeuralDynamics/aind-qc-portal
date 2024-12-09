"""QC Project App

Generates a view of a single project's asset records and a dataframe with links out to the QC pages

Intended to be the main entry point for a project's data
"""
import panel as pn
import altair as alt
import param
import pandas as pd
from aind_qc_portal.docdb.database import get_project, _raw_name_from_derived
from aind_qc_portal.utils import OUTER_STYLE, set_background, format_link, AIND_COLORS, df_timestamp_range

set_background()


class Settings(param.Parameterized):
    project_name = param.String(default="Learning mFISH-V1omFISH")


settings = Settings()
pn.state.location.sync(settings, {"project_name": "project_name"})


class ProjectView():

    def __init__(self):
        self._get_assets()

    def _get_assets(self):
        """Get all assets with this project name"""
        print(settings.project_name)
        records = get_project(settings.project_name)

        data = []
        groups = {}
        for record in records:
            raw_name = _raw_name_from_derived(record['name'])

            if raw_name not in groups:
                groups[raw_name] = len(groups)

            record_data = {
                '_id': record['_id'],
                'raw': record['data_description']['data_level'] == 'raw',
                'project_name': record['data_description']['project_name'],
                'location': record['location'],
                'name': record['name'],
                'session_start_time': record['session']['session_start_time'],
                'session_type': record['session']['session_type'],
                'subject_id': record['subject']['subject_id'],
                'genotype': record['subject']['genotype'],
                'group': groups[raw_name],
            }
            data.append(record_data)

            # Parse the asset history

        self.data = pd.DataFrame(data)
        self.data["timestamp"] = pd.to_datetime(self.data["session_start_time"])
        self.data["Date"] = self.data["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        self.data["S3 link"] = self.data["location"].apply(lambda x: format_link(x, text="S3 link"))
        self.data["Subject view"] = self.data["_id"].apply(lambda x: format_link(f"/qc_asset_app?id={x}"))
        self.data["QC view"] = self.data["_id"].apply(lambda x: format_link(f"/qc_app?id={x}"))

        self.data.sort_values(by="timestamp", ascending=True, inplace=True)
        unique_groups = self.data["group"].unique()
        group_mapping = {
            group: new_group for new_group, group in enumerate(unique_groups)
        }

        # Replace the 'group' column with the new group values
        self.data["group"] = self.data["group"].map(group_mapping)
        self.data.sort_values(by="group", ascending=True, inplace=True)

    def get_data(self):
        return self.data[["subject_id", "Date", "S3 link", "Subject view", "QC view", "genotype", "session_type", "raw"]]

    def history_panel(self):
        """Create a plot showing the history of this asset, showing how assets were derived from each other"""

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(
            self.data
        )

        chart = (
            alt.Chart(self.data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Date:T",
                    title="Time",
                    scale=alt.Scale(domain=[min_range, max_range]),
                    axis=alt.Axis(format=format, tickCount=range_unit),
                ),
                y=alt.Y("group:N", title="Raw asset"),
                tooltip=[
                    "name",
                    "session_type",
                    "subject_id",
                    "genotype",
                    "Date",
                ],
                color=alt.Color("subject_id:N"),
            )
        )

        return pn.pane.Vega(chart, sizing_mode="stretch_width", styles=OUTER_STYLE)

md = f"""
<h1 style="color:{AIND_COLORS["dark_blue"]};">
    QC Portal - Project View
</h1>
Main entrypoint for projects. Shows all assets flagged for each project and links to the QC pages.
"""

header = pn.pane.Markdown(md, width=1000, styles=OUTER_STYLE)


project_view = ProjectView()
chart_pane = project_view.history_panel()
df_pane = pn.pane.DataFrame(project_view.get_data(), width=1000, escape=False, index=False, styles=OUTER_STYLE)

col = pn.Column(header, chart_pane, df_pane)
row = pn.Row(pn.HSpacer(), col, pn.HSpacer())

row.servable(title="AIND QC - Project")
