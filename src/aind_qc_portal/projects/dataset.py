import pandas as pd
import param

from aind_qc_portal.docdb.database import get_project, get_project_custom
from aind_qc_portal.utils import format_link, qc_color
from aind_data_schema.core.quality_control import QualityControl, Status

class ProjectDataset(param.Parameterized):
    """Generic dataset class, loads default data for all projects"""
    subject_filter = param.String(default="")

    def __init__(self, project_name: str):
        """Create a ProjectDataset object"""

        self.project_name = project_name
        self._df = None
        self.exposed_columns = [
            "subject_id", "Date", "name", "Operator", "S3 link", "Status", "Subject view", "QC view", "session_type", "raw"
        ]
        self._get_assets()

    def _get_assets(self):
        """Get all assets with this project name"""
        print(self.project_name)
        records = get_project(self.project_name)

        data = []
        for record in records:
            subject_id = record.get('subject', {}).get('subject_id')

            # rig, operator, QC notes get bubbled up? qc status,
            # custom genotype mapping. Do this for learning-mfish

            # reconstruct the QC object, if possible
            if record.get('quality_control'):
                qc = QualityControl(**record.get('quality_control'))
            else:
                qc = None

            record_data = {
                '_id': record.get('_id'),
                'raw': record.get('data_description', {}).get('data_level') == 'raw',
                'project_name': record.get('data_description', {}).get('project_name'),
                'location': record.get('location'),
                'name': record.get('name'),
                'session_start_time': record.get('session', {}).get('session_start_time'),
                'session_type': record.get('session', {}).get('session_type'),
                'subject_id': subject_id,
                'operator': list(record.get('session', {}).get('experimenter_full_name')),
                'Status': qc.status().value if qc else "No QC",
            }
            data.append(record_data)

        if len(data) == 0:
            self._df = None
            return

        self._df = pd.DataFrame(data)
        self._df["timestamp"] = pd.to_datetime(self._df["session_start_time"], format='mixed', utc=True)
        self._df["Date"] = self._df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        self._df["S3 link"] = self._df["location"].apply(lambda x: format_link(x, text="S3 link"))
        self._df["Subject view"] = self._df["_id"].apply(lambda x: format_link(f"/qc_asset_app?id={x}"))
        self._df["qc_link"] = self._df["_id"].apply(lambda x: f"/qc_app?id={x}")
        self._df["QC view"] = self._df.apply(lambda row: format_link(row["qc_link"]), axis=1)
        self._df["Operator"] = self._df["operator"].apply(lambda x: ", ".join(x))
        self._df.sort_values(by="timestamp", ascending=True, inplace=True)
        self._df.sort_values(by="subject_id", ascending=False, inplace=True)

    def filtered_data(self):
        if self.subject_filter:
            filtered_df = self._df[self._df["subject_id"].str.contains(self.subject_filter, case=False, na=False)]
        else:
            filtered_df = self._df

        return filtered_df[self.exposed_columns]

    @property
    def data(self):

        return self.filtered_data()[self.exposed_columns].style.map(qc_color, subset=["Status"])


    @property
    def timestamp_data(self):
        if self.subject_filter:
            filtered_df = self._df[self._df["subject_id"].str.contains(self.subject_filter, case=False, na=False)]
        else:
            filtered_df = self._df

        return filtered_df[["timestamp"]]


class LearningmFishDataset(ProjectDataset):

    def __init__(self, project_name: str):
        if project_name != "Learning mFISH-V1omFISH":
            raise ValueError("This class is only for Learning mFISH-V1omFISH")

        super().__init__(project_name=project_name)

        self._get_mfish_assets()

    def _get_mfish_assets(self):
        """Load additional information needed for the Learning mFISH-V1omFISH project

        Extra data should be appended to the self._df dataframe and then needs to be added to the
        list of exposed columns.
        """
        data = get_project_custom(self.project_name, [""])


mapping = {
    "Learning mFISH-V1omFISH": LearningmFishDataset,
}
