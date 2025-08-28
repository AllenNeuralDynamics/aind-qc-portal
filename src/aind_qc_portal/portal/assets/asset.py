""" Individual asset panel: shows one raw asset and its derived assets """

import pandas as pd
import panel as pn
from panel.custom import PyComponent
import param

from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.assets.asset_card import RawAssetCard
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

    def records_to_df(self, records: list[dict]) -> pd.DataFrame:
        """Convert the JSON records into a DataFrame for display"""

        data = []

        for record in records:
            if "quality_control" in record and record["quality_control"]:
                qc_link = "/view?name=" + record["name"]
            else:
                qc_link = None

            # Pull out relevant fields, drop others
            data.append(
                {
                    "data_level": record.get("data_description", {}).get("data_level", ""),
                    "QC link": format_link(qc_link) if qc_link else "No QC",
                }
            )

        return pd.DataFrame(data)

    def _init_panel_components(self):
        """Initialize the components of the AssetPanel"""

        self.subject_card = RawAssetCard(
            asset_name=self.raw_record.get("name", "Unknown"),
            subject_id=self.raw_record.get("subject", {}).get("subject_id", "Unknown"),
            acquisition_start_time=self.raw_record.get("acquisition", {}).get("acquisition_start_time", "N/A"),
            project_name=self.raw_record.get("data_description", {}).get("project_name", "N/A"),
        )

        self.table = pn.pane.DataFrame(
            object=self.df,
            escape=False,
        )

        self.panel = pn.Column(
            self.subject_card,
            self.table,
            styles=OUTER_STYLE,
            sizing_mode="stretch_width",
        )

    def __panel__(self):
        """Return the Panel object for this component"""
        return self.panel
