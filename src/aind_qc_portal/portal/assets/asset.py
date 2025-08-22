""" Individual asset panel """

import panel as pn
from panel.custom import PyComponent
import param

from aind_qc_portal.portal.database import Database
from aind_qc_portal.utils import raw_name_from_derived
from aind_qc_portal.layout import OUTER_STYLE


class Asset(PyComponent):
    """Panel for an individual asset"""

    asset_chains = param.List(default=[])  # List of lists going from raw -> derived for every derived asset
    records = param.Dict(default={})  # The actual record data for all assets

    def __init__(self, derived_records: list[dict], database: Database):
        """Initialize the AssetPanel with a record"""
        super().__init__()
        self.derived_records = derived_records
        self.database = database

        self._init_panel_components()
        self._get_raw_record()

    def _get_raw_record(self):
        """Pull derived records from DocDB"""

        # Use prefix matching with regex anchor for efficient indexed search
        # This finds names that start with the current asset name followed by more content
        self.panel.loading = True
        base_name = raw_name_from_derived(self.derived_records[0]["name"])
        query = {
            "name": base_name,
            "data_description.data_level": "raw",
        }
        raw_records = self.database.get_records(query)

        if not raw_records:
            raise ValueError(f"No raw record found for derived asset {base_name}")
        self.raw_record = raw_records[0]
        self.panel.loading = False

    def _init_panel_components(self):
        """Initialize the components of the AssetPanel"""

        self.header = pn.pane.Markdown()

        self.panel = pn.Column(
            self.header,
            styles=OUTER_STYLE,
        )

    @pn.depends("raw_record", watch=True)
    def __update_header(self):
        """Update the header when the raw record changes"""
        derived_asset_names = "\n".join(
            [rec["name"] for rec in self.derived_records]
        )
        self.header.object = f"### Asset: {self.raw_record['name']}\n{derived_asset_names}"

    def __panel__(self):
        """Return the Panel object for this component"""
        return self.panel
