"""Generic curation panel for displaying curation data with media references"""

import pandas as pd
from panel.custom import PyComponent
import panel as pn
import param

from aind_qc_portal.view_contents.panels.media.media import Media


class GenericCuration(PyComponent):
    """Generic curation panel

    Dropdown menu selects keys
    "reference" keys appear as Media objects in a media pane (if present)
    Other keys appear in a table
    """

    selected_key = param.String(default="")

    def __init__(self, data: dict, bucket, prefix, raw_s3_loc=None):
        """Initialize GenericCuration panel"""
        super().__init__()

        self.data = data
        self.bucket = bucket
        self.prefix = prefix
        self.raw_s3_loc = raw_s3_loc

        keys = list(data.keys())
        self.has_references = "reference" in data[keys[0]] if keys and isinstance(data[keys[0]], dict) else False

        self._init_panel_objects()

        self._populate_data(data)


    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.dropdown = pn.widgets.Select.from_param(self.param.selected_key, name="Curation Key", options=[])
        self.table = pn.pane.DataFrame()

        if self.has_references:
            self.media = pn.Column(
                sizing_mode="stretch_width",
            )
            self.content = pn.Row(
                pn.Column(
                    self.dropdown,
                    self.table,
                ),
                self.media,
            )
        else:
            self.content = pn.Column(
                self.dropdown,
                self.table,
            )

    def _populate_data(self, data: dict):
        """Populate the dropdown and data table"""
        self.dropdown.options = list(data.keys())
        if self.dropdown.options:
            self.dropdown.value = self.dropdown.options[0]

        self.param.watch(self._populate_table, "selected_key")

        # Trigger initial population
        if self.dropdown.options:
            self._populate_table()

    def _populate_table(self, event=None):
        """Populate the data table and media pane based on the selected key"""
        key = self.selected_key
        if not key:
            self.table.object = None
            return

        record = self.data[key]

        # Build DataFrame excluding 'reference' key for cleaner display
        table_data = {k: v for k, v in record.items() if k != "reference"}
        if table_data:
            df = pd.DataFrame(table_data, index=[0]).T
            df.columns = ["Value"]
            self.table.object = df
        else:
            self.table.object = None

        if self.has_references and "reference" in record:
            reference = record["reference"]
            self.media.clear()
            media_panel = Media(
                reference=reference,
                s3_bucket=self.bucket,
                s3_prefix=self.prefix,
                raw_s3_loc=self.raw_s3_loc,
                lazy_load=False,
            )
            self.media.append(media_panel)

    def __panel__(self):
        """Return the panel representation of this component"""
        return self.content


class EphysCuration(PyComponent):
    """Ephys/Spike sorting curation panel"""

    def __init__(self, data: dict, bucket, prefix, raw_s3_loc=None, reference=None):
        """Initialize EphysCuration panel"""
        super().__init__()

        self.data = data
        self.bucket = bucket
        self.prefix = prefix
        self.raw_s3_loc = raw_s3_loc
        self.reference = reference

        self._init_panel_objects()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.json_editor = pn.pane.JSON(
            object=self.data,
            sizing_mode="stretch_width",
        )

        if self.reference:
            media_panel = Media(
                reference=self.reference,
                s3_bucket=self.bucket,
                s3_prefix=self.prefix,
                raw_s3_loc=self.raw_s3_loc,
                lazy_load=False,
            )
            self.content = pn.Row(
                self.json_editor,
                media_panel,
            )
        else:
            self.content = self.json_editor

    def __panel__(self):
        """Return the panel representation of this component"""
        return self.content
