# Searchbar
# Generates a Panel row object that integrates with DocDB to get the subject/session/date of a record
# Eventually we'll add an LLM summary of the
import panel as pn
import pandas as pd
import param
import json
from datetime import datetime

from aind_qc_portal.docdb.database import (
    get_meta,
    API_GATEWAY_HOST,
    DATABASE,
    COLLECTION,
)
from aind_qc_portal.utils import (
    ASSET_LINK_PREFIX,
    QC_LINK_PREFIX,
    qc_color,
    OUTER_STYLE,
    AIND_COLORS,
    set_background,
    format_link,
)
from aind_data_schema.core.quality_control import QualityControl

pn.extension()

set_background()


class SearchOptions(param.Parameterized):

    def __init__(self):
        """Initialize a search options object"""

        data = []
        meta_list = get_meta()

        self.shame = []

        for record in meta_list:

            record_split = record["name"].split("_")
            if len(record_split) >= 4:  # drop names that are junk

                if "quality_control" in record and record["quality_control"]:
                    # try to validate the QC object

                    try:
                        qc = QualityControl.model_validate_json(
                            json.dumps(record["quality_control"])
                        )
                        status = qc.status().value
                    except Exception as e:
                        print(f"QC object failed to validate: {e}")
                        status = "Invalid QC"
                else:
                    status = "No QC"

                # check that the date parses
                date = record_split[2]
                try:
                    datetime.fromisoformat(date)
                except ValueError:
                    self.shame.append(record["name"])
                    continue

                r = {
                    "name": record["name"],
                    "platform": record_split[0],
                    "subject_id": record_split[1],
                    "date": record_split[2],
                    "status": status,
                    "subject_view": format_link(
                        ASSET_LINK_PREFIX + record["_id"], "link"
                    ),
                    "qc_view": format_link(
                        QC_LINK_PREFIX + record["_id"], "link"
                    ),
                }
                data.append(r)
            else:
                self.shame.append(record["name"])

        self.df = pd.DataFrame(
            data,
            columns=[
                "name",
                "platform",
                "subject_id",
                "date",
                "status",
                "subject_view",
                "qc_view",
            ],
        )

        self.df = self.df.sort_values(by="date", ascending=False)

        self._subject_ids = list(sorted(set(self.df["subject_id"].values)))
        self._subject_ids.insert(0, "")
        self._modalities = list(sorted(set(self.df["platform"].values)))
        self._modalities.insert(0, "")
        self._dates = list(sorted(set(self.df["date"].values)))
        self._dates.insert(0, "")

        self.active("", "", "")

    @property
    def subject_ids(self):
        return self._subject_ids

    @property
    def modalities(self):
        return self._modalities

    @property
    def dates(self):
        return self._dates

    def active(self, modality_filter, subject_filter, date_filter):
        df = self.df.copy()

        if modality_filter != "":
            df = df[df["platform"] == modality_filter]

        if subject_filter != "":
            df = df[df["subject_id"] == subject_filter]

        if date_filter != "":
            df = df[df["date"] == date_filter]

        # Keep a copy with the name field
        self._active_names = list(set(df["name"].values))

        df = df.drop(["name"], axis=1)

        df = df.rename(
            columns={
                "platform": "Platform",
                "subject_id": "Subject ID",
                "date": "Date",
                "status": "Status",
                "subject_view": "Subject View",
                "qc_view": "QC View",
            }
        )

        return df

    def active_names(self):
        return ["Clear"] + self._active_names

    def all_names(self):
        return list(set(self.df["name"].values))


options = SearchOptions()


class SearchView(param.Parameterized):
    modality_filter = param.ObjectSelector(
        default="", objects=options.modalities
    )
    subject_filter = param.ObjectSelector(
        default="", objects=options.subject_ids
    )
    date_filter = param.ObjectSelector(default="", objects=options.dates)
    text_filter = param.String(default="")

    def __init__(self, **params):
        super().__init__(**params)

    def df_filtered(self):
        """Filter the options dataframe"""
        if self.text_filter != "" and self.text_filter != "Clear":
            return options.df[options.df["name"] == self.text_filter]

        df_filtered = options.active(
            self.modality_filter, self.subject_filter, self.date_filter
        )
        return df_filtered.style.map(qc_color, subset=["Status"])

    def df_textinput(self, value):
        print(value)
        self.text_filter = value


searchview = SearchView()
# pn.state.location.sync(searchview, {
#     'modality_filter': 'modality',
#     'subject_filter': 'subject',
#     'date_filter': 'date'
# })

text_input = pn.widgets.AutocompleteInput(
    name="Search:",
    placeholder="Name/Subject/Platform/Date",
    options=options.active_names(),
    search_strategy="includes",
    min_characters=0,
    width=660,
)


def new_class(cls, **kwargs):
    "Creates a new class which overrides parameter defaults."
    return type(type(cls).__name__, (cls,), kwargs)


search_dropdowns = pn.Param(
    searchview,
    name="Filters",
    show_name=False,
    default_layout=new_class(pn.GridBox, ncols=2),
    parameters=["modality_filter", "subject_filter", "date_filter"],
)

left_col = pn.Column(text_input, search_dropdowns)

dataframe_pane = pn.pane.DataFrame(
    searchview.df_filtered(),
    escape=False,
    sizing_mode="stretch_both",
    index=False,
)


@pn.depends(
    searchview.param.modality_filter,
    searchview.param.subject_filter,
    searchview.param.date_filter,
    watch=True,
)
def update_dataframe(*events):
    text_input.options = options.active_names()
    dataframe_pane.object = searchview.df_filtered()


def textinput_update(event):
    print(event.new)
    searchview.df_textinput(event.new)
    update_dataframe()


text_input.param.watch(textinput_update, "value")


md = f"""
<h1 style="color:{AIND_COLORS["dark_blue"]};">
    Allen Institute for Neural Dynamics - QC Portal
</h1>
This portal allows you to search all existing metadata and explore the <span style="color:{AIND_COLORS["dark_blue"]}"><b>quality control</b></span> file. Open the subject view to see the raw and derived assets related to a single record. Open the QC view to explore the quality control object for that record.
Connected to: <span style="color:{AIND_COLORS["light_blue"]}">{API_GATEWAY_HOST}/{DATABASE}/{COLLECTION}</span>
"""
header = pn.pane.Markdown(md)

col = pn.Column(
    header, left_col, dataframe_pane, min_width=700, styles=OUTER_STYLE
)

display = pn.Row(pn.HSpacer(), col, pn.HSpacer())

display.servable(title="AIND QC - Portal")
