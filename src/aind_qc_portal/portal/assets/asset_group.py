"""Panel for a group of assets selected from a query"""
import param
from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.assets.asset import Asset
from aind_qc_portal.utils import raw_name_from_derived
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

    def _format_query(self):
        """Format the query for display"""
        # Remove internal filters for display
        query_copy = self.query.copy()
        query_copy.pop("data_description.data_level", None)

        if not self.query:
            query_string = "*no query set*"
        else:
            query_string = "\n".join(f"- {k}: {v}" for k, v in query_copy.items())
        return f"## Assets pulled from query:\n{query_string}"

    def _init_panel_components(self):
        """Initialize the components of the AssetGroupPanel"""

        self.header = pn.pane.Markdown(
            self._format_query(),
            styles=OUTER_STYLE,
        )

        self.main_col = pn.Column(styles=OUTER_STYLE)
        self.panel = pn.Row(
            pn.HSpacer(), self.main_col, pn.HSpacer()
        )

    @pn.depends("query", watch=True)
    def _get_records(self):
        """Fetch records from the database based on the query"""
        print("Fetching records with query:", self.query)

        # Fetch records
        self.records = self.database.get_records(self.query) if self.query else []

        # Go through all the records and pull out the raw asset names
        # Then group records by asset name, and pass them to Asset objects
        raw_to_derived = {}
        for record in self.records:
            raw_name = raw_name_from_derived(record["name"])
            if raw_name not in raw_to_derived:
                raw_to_derived[raw_name] = []
            raw_to_derived[raw_name].append(record)

        self.header.object = self._format_query()

        self.assets = [Asset(records, self.database) for _, records in raw_to_derived.items()]

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
