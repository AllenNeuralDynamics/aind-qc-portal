""" Individual asset panel: shows one raw asset and its derived assets """

import pandas as pd
import panel as pn
from panel.custom import PyComponent
import param

from aind_qc_portal.portal.database import Database
from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.utils import format_link


class Asset(PyComponent):
    """Panel for an individual asset"""

    asset_chains = param.List(default=[])  # List of lists going from raw -> derived for every derived asset
    records = param.Dict(default={})  # The actual record data for all assets

    def __init__(self, records: list[dict], database: Database):
        """Initialize the AssetPanel with a record"""
        super().__init__()
        self.raw_record = records[0]
        self.derived_records = records[1:]
        self.df = self.records_to_df(records)
        self.database = database

        self._init_panel_components()
        self._update_header()

    def records_to_df(self, records: list[dict]) -> pd.DataFrame:
        """Convert the JSON records into a DataFrame for display"""

        data = []

        for record in records:

            if "quality_control" in record and record["quality_control"]:
                qc_link = "/view?name=" + record["name"]
            else:
                qc_link = None

            # Pull out relevant fields, drop others
            data.append({
                "data_level": record.get("data_description", {}).get("data_level", ""),
                "QC link": format_link(qc_link) if qc_link else "No QC",
            })

        return pd.DataFrame(data)

    def _init_panel_components(self):
        """Initialize the components of the AssetPanel"""

        self.header = pn.pane.Markdown()
        self._update_header()

        self.table = pn.pane.DataFrame(
            object=self.df,
            escape=False,
        )

        self.panel = pn.Column(
            self.header,
            self.table,
            styles=OUTER_STYLE,
            sizing_mode="stretch_width",
        )

    def _update_header(self):
        """Create the header"""
        derived_asset_names = ""
        for rec in self.derived_records:
            derived_asset_names += f"\n\nDerived: {rec['name']}"

        name = self.raw_record["name"] if self.raw_record else "Unknown"
        
        md = f"""
### Raw asset: {name}

Acquisition.acquisition_start_time: {self.raw_record.get("acquisition", {}).get("acquisition_start_time", "N/A")}

Subject.subject_id: {self.raw_record.get("subject", {}).get("subject_id", "N/A")}

DataDescription.project_name: {self.raw_record.get("data_description", {}).get("project_name", "N/A")}       
"""
        
        self.header.object = md

    def __panel__(self):
        """Return the Panel object for this component"""
        return self.panel
