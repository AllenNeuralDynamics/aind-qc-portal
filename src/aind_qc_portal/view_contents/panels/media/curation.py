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

    def __init__(self, data: dict, bucket, prefix):
        super().__init__()
        
        self.data = data
        self.bucket = bucket
        
        keys = list(data.keys())
        self.has_references = "reference" in data[keys[0]]

        self._init_panel_objects()
        self._populate_data(data)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.dropdown = pn.widgets.Select.from_param(
            self.param.selected_key,
            name="Curation Key",
            options=[]
        )
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
        self.dropdown.value = self.dropdown.options[0]
        
        self.param.selected_key.watch(self._populate_table, "value")

    def _populate_table(self):
        """Populate the data table and media pane based on the selected key"""
        key = self.selected_key
        if not key:
            self.table.object = None

        record = self.data[key]
        df = pd.DataFrame(record).T
        self.table.object = df

        if self.has_references and "reference" in record:
            references = record["reference"]
            self.media.clear()
            for ref in references:
                media_panel = Media(reference=ref, s3_bucket=self.bucket, s3_prefix=self.prefix)
                self.media.append(media_panel)

    def __panel__(self):
        return self.content
