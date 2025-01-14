import pandas as pd
import param

from aind_qc_portal.docdb.database import get_project
from aind_qc_portal.utils import format_link, qc_status_color_css
from aind_data_schema.core.quality_control import QualityControl


class ProjectDataset(param.Parameterized):
    """Generic dataset class, loads default data for all projects"""
    subject_filter = param.List(default=[])

    def __init__(self, project_name: str):
        """Create a ProjectDataset object"""

        self.project_name = project_name
        self._df = pd.DataFrame(columns=["_id", "timestamp"])
        self.standard_columns = [
            "subject_id", "Date", "Researcher", "S3 link", "Status", "QC view", "session_type", "raw", 
        ]
        self.exposed_columns = [
            "subject_id", "Date", "name", "Researcher", "S3 link", "Status", "QC view", "session_type", "raw", "qc_link", "timestamp"
        ]
        self._get_assets()

    def _get_assets(self):
        """Get all assets with this project name"""
        records = get_project(self.project_name)

        data = []
        for record in records:
            subject_id = record.get('subject', {}).get('subject_id')

            # rig, operator, QC notes get bubbled up? qc status,
            # custom genotype mapping. Do this for learning-mfish

            # reconstruct the QC object, if possible
            if record.get('quality_control'):
                qc = QualityControl.model_validate(record.get('quality_control'))
            else:
                qc = None

            operator_list = record.get('session', {}).get('experimenter_full_name')
            if operator_list:
                operator_list = list(operator_list)

            if record.get('session', {}):
                start_time = record.get('session', {}).get('session_start_time')
            elif record.get('acquisition', {}):
                start_time = record.get('acquisition', {}).get('session_start_time')
            else:
                start_time = None

            if record.get('session', {}):
                session_type = record.get('session', {}).get('session_type')
            elif record.get('acquisition', {}):
                session_type = record.get('acquisition', {}).get('session_type')
            else:
                session_type = None

            record_data = {
                '_id': record.get('_id'),
                'raw': record.get('data_description', {}).get('data_level') == 'raw',
                'project_name': record.get('data_description', {}).get('project_name'),
                'location': record.get('location'),
                'name': record.get('name'),
                'session_start_time': start_time,
                'session_type': session_type,
                'subject_id': subject_id,
                'operator': operator_list,
                'Status': qc.status().value if qc else "No QC",
            }
            data.append(record_data)

        if len(data) == 0:
            return

        # Rename some columns and add some additional helper columns
        self._df = pd.DataFrame(data)
        self._df["timestamp"] = pd.to_datetime(self._df["session_start_time"], format='mixed', utc=True)
        self._df["Date"] = self._df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        self._df["S3 link"] = self._df["location"].apply(lambda x: format_link(x, text="S3 link"))
        self._df["qc_link"] = self._df["_id"].apply(lambda x: f"/qc_app?id={x}")
        self._df["QC view"] = self._df.apply(lambda row: format_link(row["qc_link"]), axis=1)
        self._df["Researcher"] = self._df["operator"].apply(lambda x: ", ".join(x) if x else None)

        # Sort dataframe by time and then by subject ID
        self._df.sort_values(by="timestamp", ascending=True, inplace=True)
        self._df.sort_values(by="subject_id", ascending=False, inplace=True)

        self._df.to_csv('data.csv')

    @property
    def _data_filtered(self) -> pd.DataFrame:
        """Internal access method to get the full filtered dataframe

        Returns
        -------
        pd.DataFrame
        """
        if len(self.subject_filter) > 0:
            filtered_df = self._df[self._df["subject_id"].isin(self.subject_filter)]
        else:
            filtered_df = self._df

        return filtered_df

    def data_filtered(self, standard_columns=False) -> pd.DataFrame:
        """Return a filtered dataframe based on the subject filter

        Returns
        -------
        pd.DataFrame
        """
        filtered_df = self._data_filtered

        columns = self.standard_columns if standard_columns else self.exposed_columns

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

        return self.data_filtered(standard_columns=True).style.map(qc_status_color_css, subset=["Status"])

    @property
    def data(self) -> pd.DataFrame:
        """Return the raw data
        """
        if self._df is not None:
            return self._df
        else:
            raise ValueError("No data found")

    @property
    def timestamps(self):
        filtered_df = self._data_filtered

        return filtered_df[["timestamp"]]
