"""Panel for a group of assets selected from a query"""
import param
from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.assets.asset import Asset
from aind_qc_portal.layout import OUTER_STYLE
from panel.custom import PyComponent
import panel as pn


class AssetGroup(PyComponent):
    """Panel for a group of assets selected from a query"""

    query = param.Dict(default={})
    records = param.List(default=[])
    assets = param.List(default=[])

    def __init__(self, query: dict, database: Database):
        """Initialize the AssetGroupPanel with a query and database"""
        super().__init__()
        self.query = query
        self.database = database

        self._init_panel_components()

    def update_query(self, query: dict):
        """Update the query and fetch new records"""
        self.panel.loading = True
        self.query = query

    def _init_panel_components(self):
        """Initialize the components of the AssetGroupPanel"""
        self.header_md = pn.pane.Markdown("## Asset Group\nQuery:", width=500)

        self.query_panel = pn.widgets.JSONEditor(mode="text", width=500, menu=False)
        self.query_panel.link(self, value="query", bidirectional=True)

        self.header = pn.Column(
            self.header_md,
            self.query_panel,
        )

        self.main_col = pn.Column(
            styles=OUTER_STYLE,
            width=1200,
        )
        self.panel = pn.Row(
            pn.HSpacer(), self.main_col, pn.HSpacer()
        )

    @pn.depends("query", watch=True)
    def _get_records(self):
        """Fetch records from the database based on the query"""
        print("Fetching records with query:", self.query)

        # Fetch records
        self.records = self.database.get_records(self.query) if self.query else []

        # Store the records as [raw, derived0, derived1, ...]
        raw_to_records = {}
        
        # Split records into raw and derived
        raw_records = [rec for rec in self.records if rec["data_description"]["data_level"] == "raw"]
        derived_records = [rec for rec in self.records if rec["data_description"]["data_level"] != "raw"]
        # Pre-sort records by acquisition.acquisition_start_time
        raw_records.sort(key=lambda r: r.get("acquisition", {}).get("acquisition_start_time", ""), reverse=True)
        derived_records.sort(key=lambda r: r.get("acquisition", {}).get("acquisition_start_time", ""), reverse=True)

        # Put the raw records first
        for record in raw_records:
            raw_to_records[record["name"]] = [record]

        for record in derived_records:
            if "source_data" in record["data_description"] and record["data_description"]["source_data"]:
                raw_to_records[record["data_description"]["source_data"][0]].append(record)

        self.assets = [Asset(records, self.database) for _, records in raw_to_records.items()]

    @pn.depends("assets", watch=True)
    def _update_assets(self):
        """Update the asset panels when records change"""
        record_count = len(self.records) if self.records else 0
        print(f"Updating assets, {record_count} records found")
        # Hide loading spinner when records are updated
        self.main_col.objects = [
            self.header,
            *self.assets
        ]
        self.panel.loading = False

    def __panel__(self):
        return self.panel
