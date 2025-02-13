"""Dataset class for a project"""

from datetime import datetime
import pandas as pd
import panel as pn
import param

from aind_qc_portal.docdb.database import get_project_data
from aind_qc_portal.utils import (
    format_link,
    qc_status_color_css,
    qc_status_link_html,
)
from aind_data_schema.core.quality_control import QualityControl, Status

ALWAYS_COLUMNS = ["Subject ID", "Acquisition Time"]
DEFAULT_COLUMNS = ["Researcher", "QC Status", "Type"]
HIDDEN_COLUMNS = ["timestamp", "session_start_time", "project_name", "qc_link"]

QC_STATUS_OPTIONS = [
    "All",
    "No QC",
    Status.PASS.value,
    Status.FAIL.value,
    Status.PENDING.value,
]


class ProjectDataset(param.Parameterized):
    """Generic dataset class, loads default data for all projects"""

    subject_filter = param.List(default=[])
    columns_filter = param.List(default=ALWAYS_COLUMNS + DEFAULT_COLUMNS)
    derived_filter = param.String(default="All")
    type_filter = param.String(default="All")
    status_filter = param.String(default="All")

    def __init__(self, project_name: str, **params):
        """Create a ProjectDataset object"""
        super().__init__(**params)

        self.project_name = project_name
        self._df = pd.DataFrame(columns=["_id", "timestamp"])

        self.subject_selector = pn.widgets.MultiChoice(name="Subject ID")
        self.columns_selector = pn.widgets.MultiChoice(name="Columns")
        self.derived_selector = pn.widgets.Select(
            name="Derived", options=["All", "Raw", "Derived"]
        )
        self.type_selector = pn.widgets.Select(name="Type")
        self.status_selector = pn.widgets.Select(
            name="QC Status", options=QC_STATUS_OPTIONS
        )

        self._get_assets()

        self.subject_selector.options = self.subjects
        self.columns_selector.options = [
            column
            for column in self.columns
            if column not in ALWAYS_COLUMNS + HIDDEN_COLUMNS
        ]
        self.type_selector.options = ["All"] + self.types

    def _parse_session_type(self, record):
        """ Parse the session type from the record"""
        session_type = None
        if record.get("session", {}):
            session_type = record.get("session", {}).get("session_type")
        elif record.get("acquisition", {}):
            session_type = record.get("acquisition", {}).get(
                "session_type"
            )
        return session_type

    def _parse_asset(self, record):
        """Parse the basic dataset columns from the records"""
        subject_id = record.get("subject", {}).get("subject_id")
        qc = None
        start_time = None
        session_type = self._parse_session_type(record)
        processing_time = None

        # rig, operator, QC notes get bubbled up? qc status,
        # custom genotype mapping. Do this for learning-mfish

        # reconstruct the QC object, if possible
        qc = None
        if record.get("quality_control"):
            qc = QualityControl.model_validate(
                record.get("quality_control")
            )

        operator_list = record.get("session", {}).get(
            "experimenter_full_name"
        )
        if operator_list:
            operator_list = list(operator_list)

        if record.get("session", {}):
            start_time = record.get("session", {}).get(
                "session_start_time"
            )
        elif record.get("acquisition", {}):
            start_time = record.get("acquisition", {}).get(
                "session_start_time"
            )

        # parse processing time
        try:
            if record.get("processing", {}):
                data_processes = (
                    record.get("processing", {})
                    .get("processing_pipeline", {})
                    .get("data_processes", [])
                )
                if len(data_processes) > 0:
                    # convert to datetime from 2025-02-08T00:06:31.973872Z
                    processing_time = datetime.strptime(
                        data_processes[-1].get("end_date_time"),
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                    )
        except Exception as e:
            id = record.get("_id")
            print(f"Error in {id} parsing processing time: {e}")

        record_data = {
            "_id": record.get("_id"),
            "Raw Data": record.get("data_description", {}).get(
                "data_level"
            )
            == "raw",
            "project_name": record.get("data_description", {}).get(
                "project_name"
            ),
            "location": record.get("location"),
            "name": record.get("name"),
            "session_start_time": start_time,
            "Type": session_type,
            "Subject ID": subject_id,
            "operator": operator_list,
            "QC Status": qc.status().value if qc else "No QC",
            "Processing Time": processing_time,
        }
        return record_data

    def _get_assets(self):
        """Get all assets with this project name"""
        records = get_project_data(self.project_name)

        data = [self._parse_asset(record) for record in records]

        if len(data) == 0:
            return

        # Rename some columns and add some additional helper columns
        self._df = pd.DataFrame(data)
        self._df["timestamp"] = pd.to_datetime(
            self._df["session_start_time"], format="mixed", utc=True
        )
        self._df["Acquisition Time"] = self._df["timestamp"].dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self._df["S3 link"] = self._df["location"].apply(
            lambda x: format_link(x, text="S3 link")
        )
        self._df["qc_link"] = self._df["_id"].apply(
            lambda x: f"/qc_app?id={x}"
        )
        self._df["QC view"] = self._df.apply(
            lambda row: format_link(row["qc_link"]), axis=1
        )
        self._df["Researcher"] = self._df["operator"].apply(
            lambda x: ", ".join(x) if x else None
        )
        self._df["QC Status"] = self._df.apply(
            lambda row: qc_status_link_html(
                row["QC Status"], row["qc_link"], row["QC Status"]
            ),
            axis=1,
        )
        print(self._df["QC Status"].values[0])

        self._df.drop(
            columns=["qc_link", "operator", "session_start_time", "location"]
        )

        # Sort dataframe by time and then by subject ID
        self._df.sort_values(by="timestamp", ascending=True, inplace=True)
        self._df.sort_values(by="Subject ID", ascending=False, inplace=True)

    @property
    def _data_filtered(self) -> pd.DataFrame:
        """Internal access method to get the full filtered dataframe

        Returns
        -------
        pd.DataFrame
        """
        filtered_df = self._df.copy()

        if len(self.subject_filter) > 0:
            filtered_df = filtered_df[
                filtered_df["Subject ID"].isin(self.subject_filter)
            ]

        if self.derived_filter != "All":
            filtered_df = filtered_df[
                filtered_df["Raw Data"]
                == (True if self.derived_filter == "Raw" else False)
            ]

        if self.type_filter != "All":
            filtered_df = filtered_df[filtered_df["Type"] == self.type_filter]

        if self.status_filter != "All":
            filtered_df = filtered_df[
                filtered_df["QC Status"] == self.status_filter
            ]

        return filtered_df

    def data_filtered(self) -> pd.DataFrame:
        """Return a filtered dataframe based on the subject filter

        Returns
        -------
        pd.DataFrame
        """
        filtered_df = self._data_filtered

        columns = list(self.columns_filter)

        if filtered_df is not None:
            return filtered_df[columns]
        else:
            return pd.DataFrame(columns=columns)

    @property
    def data_styled(self):
        """Return a styled dataframe with color coding for QC status

        Returns
        -------
        pd.DataFrame
        """

        return self.data_filtered().style.map(
            qc_status_color_css, subset=["Status"]
        )

    @property
    def data(self) -> pd.DataFrame:
        """Return the raw data"""
        if self._df is not None:
            return self._df
        else:
            raise ValueError("No data found")

    @property
    def subjects(self):
        """ Return the unique subject IDs"""
        return list(self._df["Subject ID"].unique())

    @property
    def timestamps(self):
        """ Return the timestamps"""
        filtered_df = self._data_filtered

        return filtered_df[["timestamp"]]

    @property
    def columns(self):
        """ Return the columns"""
        columns = ALWAYS_COLUMNS + DEFAULT_COLUMNS + list(self._df.columns)
        return list(set(columns))

    @property
    def types(self):
        """ Return the unique session types"""
        return list(self._df["Type"].unique())

    def panel(self):
        """Return the settings panel for this dataset"""

        col = pn.Column(
            self.subject_selector,
            self.columns_selector,
            self.derived_selector,
            self.type_selector,
            self.status_selector,
        )

        return col
