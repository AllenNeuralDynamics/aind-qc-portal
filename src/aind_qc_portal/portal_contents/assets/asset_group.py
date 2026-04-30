"""Panel for a group of assets selected from a query"""

from datetime import datetime

import pandas as pd
import panel as pn
import param
from aind_metadata_utils.data_assets import co_id_to_co_link
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.portal_contents.database import Database
from aind_qc_portal.portal_contents.settings import settings
from aind_qc_portal.utils import format_link


class AssetGroup(PyComponent):
    """Panel for a group of assets selected from a query"""

    query = param.Dict(default={})
    records = param.List(default=[])
    df = param.DataFrame(default=pd.DataFrame())
    derived_data_map = param.Dict(default={})  # Make this a param so updates are tracked

    def __init__(self, query: dict, database: Database):
        """Initialize the AssetGroupPanel with a query and database"""
        super().__init__()
        self.query = query
        self.database = database

        self._init_panel_components()

        # Watch for changes in settings
        settings.param.watch(self._update_header_visibility, "show_query_editor")

    def update_query(self, query: dict):
        """Update the query and fetch new records"""
        self.panel.loading = True
        self.query = query

    def _init_panel_components(self):
        """Initialize the components of the AssetGroupPanel"""
        self.header_md = pn.pane.Markdown("## Query:", width=500)

        self.query_panel = pn.widgets.JSONEditor(mode="text", width=500, menu=False)
        self.query_panel.link(self, value="query", bidirectional=True)

        self.header = pn.Column(
            self.header_md,
            self.query_panel,
        )

        # Create the Tabulator widget with row_content for derived assets
        self.tabulator = pn.widgets.Tabulator(
            value=self.df,
            pagination="local",
            page_size=50,
            layout="fit_data_table",
            sizing_mode="stretch_width",
            show_index=False,
            header_filters=True,
            configuration={
                "rowHeight": 35,
                "headerSort": True,
            },
            widths={
                "Subject ID": 120,
                "Acquisition Time (local)": 220,
            },
        )

        self.main_col = pn.Column(
            styles=OUTER_STYLE,
            width=1200,
        )
        self.panel = pn.Row(pn.HSpacer(), self.main_col, pn.HSpacer())

        # Set initial header visibility
        self._update_header_visibility()

    def _update_header_visibility(self, event=None):
        """Update the visibility of the query header based on settings"""
        # Update main column objects based on header visibility
        if settings.show_query_editor:
            if self.header not in self.main_col.objects:
                self.main_col.objects = [self.header, self.tabulator]
        else:
            if self.header in self.main_col.objects:
                self.main_col.objects = [self.tabulator]

    def _format_raw_record_row(self, record: dict) -> dict:
        """Format a raw record into a row dict for the main table"""
        # Get metadata fields
        acquisition_time = record.get("acquisition", {}).get("acquisition_start_time", "")
        subject_id = record.get("subject", {}).get("subject_id", "")
        project_name = record.get("data_description", {}).get("project_name", "")
        genotype = record.get("subject", {}).get("subject_details", {}).get("genotype", "")

        # Format acquisition time for display
        try:
            acquisition_display = datetime.fromisoformat(acquisition_time).strftime("%Y-%m-%d %H:%M%z")
        except Exception:
            acquisition_display = acquisition_time

        return {
            "Subject ID": subject_id,
            "Acquisition Time (local)": acquisition_display,
            "Project": project_name,
            "Genotype": genotype,
        }

    def _format_derived_record_row(self, record: dict) -> dict:
        """Format a record into a row dict for the nested table (works for both raw and derived)"""
        # Get processed date
        processes = record.get("processing", {}).get("data_processes", [])
        if processes:
            process_datetime = processes[-1].get("start_date_time", "")
            try:
                processed_display = datetime.fromisoformat(process_datetime).strftime("%Y-%m-%d")
            except Exception:
                processed_display = process_datetime if process_datetime else ""
        else:
            # For raw records, use acquisition time
            acquisition_time = record.get("acquisition", {}).get("acquisition_start_time", "")
            if acquisition_time:
                try:
                    processed_display = datetime.fromisoformat(acquisition_time).strftime("%Y-%m-%d")
                except Exception:
                    processed_display = acquisition_time if acquisition_time else ""
            else:
                processed_display = ""

        modalities = record.get("data_description", {}).get("modalities", [])
        if modalities:
            processed_modalities = ", ".join([mod["abbreviation"] for mod in modalities])
        else:
            processed_modalities = ""

        # Build CO link
        co_id = record.get("other_identifiers", {}).get("Code Ocean", [])
        if co_id and isinstance(co_id, list):
            co_id = co_id[0]
        co_html = co_id_to_co_link(co_id) if co_id else "No S3"

        # Build QC link
        if "quality_control" in record and record["quality_control"]:
            qc_link = "/view?name=" + record["name"]
            qc_html = format_link(qc_link, "QC")
        else:
            qc_html = "No QC"

        return {
            "Data Level": record.get("data_description", {}).get("data_level", ""),
            "Processed": processed_display,
            "Modalities": processed_modalities,
            "CO Link": co_html,
            "QC Link": qc_html,
        }

    def _records_to_dataframe(self, records: list[dict]) -> tuple[pd.DataFrame, dict]:
        """Convert records to a DataFrame with raw assets and a dict mapping indices to derived data"""

        if not records:
            return pd.DataFrame(), {}

        # Store the records as {raw_name: [raw_record, derived_record1, ...]}
        raw_to_records = {}

        # Split records into raw and derived
        raw_records = [rec for rec in records if rec["data_description"]["data_level"] == "raw"]
        derived_records = [rec for rec in records if rec["data_description"]["data_level"] != "raw"]

        # Pre-sort records by acquisition.acquisition_start_time
        raw_records.sort(key=lambda r: r.get("acquisition", {}).get("acquisition_start_time", ""), reverse=True)
        derived_records.sort(key=lambda r: r.get("acquisition", {}).get("acquisition_start_time", ""), reverse=True)

        # Put the raw records first
        for record in raw_records:
            raw_to_records[record["name"]] = [record]

        for record in derived_records:
            if "source_data" in record["data_description"] and record["data_description"]["source_data"]:
                source_name = record["data_description"]["source_data"][0]
                if source_name in raw_to_records:
                    raw_to_records[source_name].append(record)
                else:
                    # Handle orphaned derived assets
                    raw_to_records[source_name] = [record]

        # Create rows for raw assets only, store all assets (raw + derived) in derived_data_map
        rows = []
        derived_data_map = {}

        for idx, (raw_name, asset_records) in enumerate(raw_to_records.items()):
            raw_record = asset_records[0]

            # Create the main row for the raw asset
            row = self._format_raw_record_row(raw_record)
            rows.append(row)

            # Sort assets: raw first, then derived by processing date (earliest first)
            def get_sort_key(rec):
                """Return a tuple for sorting: raw records first, then derived by processing date"""
                if rec["data_description"]["data_level"] == "raw":
                    return (0, "")  # Raw records come first

                # For derived records, get the processing date
                processes = rec.get("processing", {}).get("data_processes", [])
                if processes:
                    process_datetime = processes[-1].get("start_date_time", "")
                else:
                    process_datetime = ""

                return (1, process_datetime)  # Derived records sorted by date

            sorted_assets = sorted(asset_records, key=get_sort_key)

            # Store all assets (raw + derived) in the dropdown table
            all_rows = [self._format_derived_record_row(rec) for rec in sorted_assets]
            derived_data_map[idx] = pd.DataFrame(all_rows)

        return pd.DataFrame(rows), derived_data_map

    @pn.depends("query", watch=True)
    def _get_records(self):
        """Fetch records from the database based on the query"""
        print("Fetching records with query:", self.query)

        # Fetch records
        self.records = self.database.get_records(self.query) if self.query else []

        # Convert to dataframe and store derived data map
        # Use batch_call_watchers so both params update before _update_table fires
        df, derived_data_map = self._records_to_dataframe(self.records)
        with param.batch_call_watchers(self):
            self.df = df
            self.derived_data_map = derived_data_map

    def _create_derived_table(self, row):
        """Create a tabulator for all assets (raw + derived)"""

        # Get the row index from the dataframe
        row_idx = row.name if hasattr(row, "name") else None

        if row_idx is None or row_idx not in self.derived_data_map:
            return pn.pane.Markdown("*No assets found*")

        derived_data = self.derived_data_map[row_idx]

        # Create a mini tabulator for all assets (raw + derived)
        derived_table = pn.widgets.Tabulator(
            derived_data,
            layout="fit_data_table",
            sizing_mode="stretch_width",
            show_index=False,
            widths={
                "Data Level": 80,
                "Processed": 120,
                "CO Link": 100,
                "QC Link": 100,
            },
            configuration={
                "rowHeight": 30,
            },
            formatters={
                "CO Link": {"type": "html"},
                "QC Link": {"type": "html"},
            },
        )
        return derived_table

    @pn.depends("df", "derived_data_map", watch=True)
    def _update_table(self):
        """Update the tabulator when dataframe changes"""
        record_count = len(self.records) if self.records else 0
        print(f"Updating table, {record_count} records found")

        # Update the tabulator value
        self.tabulator.value = self.df

        # Set up row_content to show derived assets if there are any
        if self.derived_data_map:
            self.tabulator.row_content = self._create_derived_table
        else:
            self.tabulator.row_content = None

        # Update main column objects based on header visibility
        if settings.show_query_editor:
            self.main_col.objects = [self.header, self.tabulator]
        else:
            self.main_col.objects = [self.tabulator]

        # Hide loading spinner when table is updated
        self.panel.loading = False

    def __panel__(self):
        """Return the Panel representation of the AssetGroup"""
        return self.panel
