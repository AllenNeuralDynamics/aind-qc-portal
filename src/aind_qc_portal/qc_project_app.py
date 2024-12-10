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


class ProjectView(param.Parameterized):
    subject_filter = param.String(default="")

    def __init__(self):
        self._get_assets()

    def _get_assets(self):
        """Get all assets with this project name"""
        print(settings.project_name)
        records = get_project(settings.project_name)

        data = []
        for record in records:
            raw_name = _raw_name_from_derived(record['name'])
            subject_id = record.get('subject', {}).get('subject_id')

            record_data = {
                '_id': record.get('_id'),
                'raw': record.get('data_description', {}).get('data_level') == 'raw',
                'project_name': record.get('data_description', {}).get('project_name'),
                'location': record.get('location'),
                'name': record.get('name'),
                'session_start_time': record.get('session', {}).get('session_start_time'),
                'session_type': record.get('session', {}).get('session_type'),
                'subject_id': subject_id,
                'genotype': record.get('subject', {}).get('genotype'),
            }
            data.append(record_data)

        if len(data) == 0:
            self.data = None
            return

        self.data = pd.DataFrame(data)
        self.data["timestamp"] = pd.to_datetime(self.data["session_start_time"], format='mixed', utc=True)
        self.data["Date"] = self.data["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        self.data["S3 link"] = self.data["location"].apply(lambda x: format_link(x, text="S3 link"))
        self.data["Subject view"] = self.data["_id"].apply(lambda x: format_link(f"/qc_asset_app?id={x}"))
        self.data["QC view"] = self.data["_id"].apply(lambda x: format_link(f"/qc_app?id={x}"))

        self.data.sort_values(by="timestamp", ascending=True, inplace=True)
        self.data.sort_values(by="subject_id", ascending=True, inplace=True)

    def get_subjects(self):
        if self.data is None:
            return []

        return self.data["subject_id"].unique()

    def get_data(self):
        if self.data is None:
            return None
        
        if self.subject_filter:
            filtered_df = self.data[self.data["subject_id"].str.contains(self.subject_filter, case=False, na=False)]
        else:
            filtered_df = self.data

        return filtered_df[["subject_id", "Date", "S3 link", "Subject view", "QC view", "genotype", "session_type", "raw"]]

    def history_panel(self):
        """Create a plot showing the history of this asset, showing how assets were derived from each other"""
        if self.data is None:
            return pn.widgets.StaticText(
                value=f"No data found for project: {settings.project_name}"
            )

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
                y=alt.Y("subject_id:N", title="Subject ID"),
                tooltip=[
                    "name",
                    "session_type",
                    "subject_id",
                    "genotype",
                    "Date",
                ],
                color=alt.Color("subject_id:N"),
            )
            .properties(width=900)
        )

        return pn.pane.Vega(chart, sizing_mode="stretch_width", styles=OUTER_STYLE)

project_view = ProjectView()

md = f"""
<h1 style="color:{AIND_COLORS["dark_blue"]};">
    {settings.project_name}
</h1>
<b>{len(project_view.data)}</b> data assets are associated with this project.
"""

header = pn.pane.Markdown(md, width=1000, styles=OUTER_STYLE)


chart_pane = project_view.history_panel()

df_pane = pn.pane.DataFrame(project_view.get_data(), width=950, escape=False, index=False)


def update_subject_filter(event):
    project_view.subject_filter = event.new
    df_pane.object = project_view.get_data()


subject_filter = pn.widgets.Select(name="Subject filter", options=list(project_view.get_subjects()))
subject_filter.param.watch(update_subject_filter, "value")

df_col = pn.Column(subject_filter, df_pane, styles=OUTER_STYLE)

col = pn.Column(header, chart_pane, df_col)
row = pn.Row(pn.HSpacer(), col, pn.HSpacer())

row.servable(title="AIND QC - Project")
