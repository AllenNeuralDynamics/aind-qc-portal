import json
from datetime import datetime

import altair as alt
import pandas as pd
import panel as pn
import param
from aind_data_schema.core.quality_control import QualityControl

from aind_qc_portal.docdb.database import (
    _raw_name_from_derived,
    get_assets_by_subj,
    get_subj_from_id,
)
from aind_qc_portal.utils import (
    QC_LINK_PREFIX,
    df_timestamp_range,
    qc_color,
    AIND_COLORS,
    OUTER_STYLE,
    set_background,
)

alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")

set_background()


class AssetHistory(param.Parameterized):
    id = param.String(default="a61f285e-c79b-46cd-b554-991d711b6e53")

    def __init__(self, **params):
        super().__init__(**params)
        self.update()

    @pn.depends("id", watch=True)
    def update(self):
        self.has_id = True

        self.asset_name = get_subj_from_id(str(self.id))

        if self.asset_name:
            self._records = get_assets_by_subj(self.asset_name)
            self.parse_records()
        else:
            self.df = None

    @property
    def records(self):
        if self.has_id and self.df is not None:
            return self._records
        else:
            return {}

    def parse_records(self):
        """Go through the records, pulling from the name to figure out the order of events

        If the input_data_name field is in data_description, we can also use that first
        """
        if not self.has_id:
            return

        data = []
        groups = {}

        # [TODO] this is designed as-is because the current metadata records are all missing the input_data_name field, unfortunately
        for record in self._records:

            name_split = record["name"].split("_")

            raw_name = _raw_name_from_derived(record["name"])

            # keep track of groups
            if raw_name not in groups:
                groups[raw_name] = len(groups)

            if len(name_split) == 4:
                # raw asset
                modality = name_split[0]
                subject_id = name_split[1]
                date = name_split[2]
                time = name_split[3]
                type_label = "raw"
            elif len(name_split) == 7:
                # derived asset
                modality = name_split[0]
                subject_id = name_split[1]
                date = name_split[5]
                time = name_split[6]
                type_label = name_split[4]

            if "quality_control" in record and record["quality_control"]:
                qc = QualityControl.model_validate_json(
                    json.dumps(record["quality_control"])
                )
                status = qc.status().value
            else:
                status = "No QC"

            raw_date = datetime.strptime(f"{date}_{time}", "%Y-%m-%d_%H-%M-%S")

            qc_link = f'<a href="{QC_LINK_PREFIX}{record["_id"]}" target="_blank">link</a>'

            data.append(
                {
                    "name": record["name"],
                    "modality": modality,
                    "subject_id": subject_id,
                    "timestamp": pd.to_datetime(raw_date),
                    "type": type_label,
                    "status": status,
                    "qc_view": qc_link,
                    "id": record["_id"],
                    "group": groups[raw_name],
                }
            )

        self.df = pd.DataFrame(
            data,
            columns=[
                "name",
                "modality",
                "subject_id",
                "timestamp",
                "type",
                "status",
                "qc_view",
                "id",
                "group",
            ],
        )
        self.df.sort_values(by="timestamp", ascending=True, inplace=True)
        unique_groups = self.df["group"].unique()
        group_mapping = {
            group: new_group for new_group, group in enumerate(unique_groups)
        }

        # Replace the 'group' column with the new group values
        self.df["group"] = self.df["group"].map(group_mapping)
        self.df.sort_values(by="group", ascending=True, inplace=True)

    def asset_history_panel(self):
        """Create a plot showing the history of this asset, showing how assets were derived from each other"""
        if not self.has_id:
            return "No ID is set"
        if self.df is None:
            return pn.widgets.StaticText(
                value=f"No data found for ID: {self.id}"
            )

        # Calculate the time range to show on the x axis
        (min_range, max_range, range_unit, format) = df_timestamp_range(
            self.df
        )

        chart = (
            alt.Chart(self.df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "timestamp:T",
                    title="Time",
                    scale=alt.Scale(domain=[min_range, max_range]),
                    axis=alt.Axis(format=format, tickCount=range_unit),
                ),
                y=alt.Y("group:N", title="Raw asset"),
                tooltip=[
                    "name",
                    "modality",
                    "subject_id",
                    "timestamp",
                    "status",
                ],
                color=alt.Color("type:N"),
            )
            .properties(width=600, height=300, title="Asset history")
        )

        return pn.pane.Vega(chart)

    def asset_history_df(self, group: int = 0):
        """Todo"""
        if not self.has_id:
            return pd.DataFrame()

        df = self.df.copy()
        df = df[df["group"] == group]
        df = df.drop(["name", "id", "group"], axis=1)

        df = df.rename(
            columns={
                "name": "Name",
                "modality": "Modality",
                "subject_id": "Subject ID",
                "timestamp": "Date",
                "type": "Type",
                "status": "Status",
                "qc_view": "QC View",
            }
        )

        return df.style.map(qc_color, subset=["Status"])

    def panel(self):
        if self.df is not None:
            panes = []
            for group in set(self.df["group"]):
                panes.append(
                    pn.pane.DataFrame(
                        self.asset_history_df(group),
                        index=False,
                        escape=False,
                        width=660,
                    )
                )

            return pn.Column(*panes)
        else:
            return pn.pane.Markdown("")


asset_history = AssetHistory()
pn.state.location.sync(
    asset_history,
    {
        "id": "id",
    },
)

if asset_history.id == "":
    error_string = "\n## An ID must be provided as a query string. Please go back to the portal and choose an asset from the list."
else:
    error_string = ""

md = f"""
<h1 style="color:{AIND_COLORS["dark_blue"]};">
    QC Portal - Subject View
</h1>
This view shows the history of a single subject's asset records, back to their original raw dataset along with any derived assets. Select a single asset to view its quality control data.
{error_string}
"""

header = pn.pane.Markdown(md, max_width=660)

chart = asset_history.asset_history_panel()

json_pane = pn.pane.JSON(asset_history.records)

col = pn.Column(
    header,
    chart,
    asset_history.panel(),
    json_pane,
    min_width=660,
    styles=OUTER_STYLE,
)

# Create the layout
display = pn.Row(pn.HSpacer(), col, pn.HSpacer())

display.servable(title="AIND QC - Subject")
