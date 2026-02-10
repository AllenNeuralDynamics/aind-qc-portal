"""Generic curation panel for displaying curation data with media references"""

from urllib.parse import unquote

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent
from panel.reactive import ReactiveHTML

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
        first_is_dict = keys and isinstance(data[keys[0]], dict)
        self.has_references = "reference" in data[keys[0]] if first_is_dict else False

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


class EphysIframe(ReactiveHTML):
    """ReactiveHTML iframe component with message posting"""

    iframe_src = param.String(default="")
    curation_message = param.Dict(default={})

    _template = """
    <iframe id="ephys_iframe"
            src="${iframe_src}"
            style="width: 100%; height: 100%; border: none;">
    </iframe>
    """

    _scripts = {
        "curation_message": """
            const msg_len = Object.keys(data.curation_message).length;
            if (msg_len > 0 && ephys_iframe) {
                console.log('[EphysIframe] Sending curation data');
                console.log('[EphysIframe] Message:', data.curation_message);

                const message = {
                    payload: {
                        type: 'curation-data',
                        data: data.curation_message
                    }
                };

                try {
                    ephys_iframe.contentWindow.postMessage(message, '*');
                    console.log('[EphysIframe] Message sent');
                } catch (e) {
                    console.error('[EphysIframe] Error:', e);
                }
            }
        """,
        "after_layout": """
            console.log('[EphysIframe] Component rendered');
        """,
    }

    _dom_events = {"ephys_iframe": ["load"]}

    def _ephys_iframe_load(self, event):
        """Resend curation data when iframe loads"""
        print("[EphysIframe] Iframe loaded, resending curation data")
        if self.curation_message:
            temp = self.curation_message
            self.curation_message = {}
            self.curation_message = temp


class EphysCuration(PyComponent):
    """Ephys/Spike sorting curation panel"""

    selected_curation_index = param.Integer(default=0)

    def __init__(
        self,
        data: dict,
        bucket,
        prefix,
        raw_s3_loc=None,
        reference=None,
        value_callback=None,
        curation_values=None,
        curation_history=None,
    ):
        """Initialize EphysCuration panel

        Parameters
        ----------
        data : dict
            Current curation data
        bucket : str
            S3 bucket name
        prefix : str
            S3 prefix
        raw_s3_loc : str, optional
            Raw asset S3 location
        reference : str, optional
            Media reference URL
        value_callback : callable, optional
            Callback for value updates
        curation_values : list, optional
            List of curation dictionaries (most recent last)
        curation_history : dict, optional
            History information about curations
        """
        super().__init__()

        self.bucket = bucket
        self.prefix = prefix
        self.raw_s3_loc = raw_s3_loc
        self.reference = reference
        self.value_callback = value_callback

        self.curation_values = curation_values or [data]
        self.curation_history = curation_history or {}
        self.data = self.curation_values[-1] if self.curation_values else data
        self.iframe_component = None

        self._init_panel_objects()
        self._send_curation_to_iframe()

    def _init_panel_objects(self):
        """Initialize panel objects"""
        self.json_editor = pn.pane.JSON(
            object=self.data,
        )

        curation_options = self._build_curation_options()
        self.curation_dropdown = pn.widgets.Select.from_param(
            self.param.selected_curation_index, name="Select Curation", options=curation_options
        )
        self.param.watch(self._on_curation_selection_change, "selected_curation_index")

        self.metadata_pane = pn.pane.Markdown("", sizing_mode="stretch_width")
        self._update_metadata_display()

        if self.reference:
            processed_url = self._process_ephys_url(self.reference)
            print(f"EphysCuration: Processed ephys GUI URL: {processed_url}")
            self.iframe_component = EphysIframe(
                iframe_src=processed_url,
                sizing_mode="stretch_both",
            )

            self.content = pn.Row(
                pn.Column(
                    self.curation_dropdown,
                    self.metadata_pane,
                    self.json_editor,
                ),
                self.iframe_component,
            )
        else:
            self.content = pn.Column(
                self.curation_dropdown,
                self.metadata_pane,
                self.json_editor,
            )

    def _build_curation_options(self):
        """Build dropdown options from curation history"""
        options = {}
        for i in range(len(self.curation_values)):
            if i < len(self.curation_history):
                history_entry = self.curation_history[i]
                curator = history_entry.get("curator", "Unknown")
                timestamp = history_entry.get("timestamp", "")
                if "." in timestamp:
                    timestamp = timestamp.split(".")[0]
                label = f"{curator} - {timestamp}"
            else:
                label = f"Curation {i}"
            options[label] = i
        return options

    def _on_curation_selection_change(self, event=None):
        """Handle curation selection change"""
        self.data = self.curation_values[self.selected_curation_index]
        self.json_editor.object = self.data
        self._update_metadata_display()
        self._send_curation_to_iframe()

    def _update_metadata_display(self):
        """Update metadata display for the selected curation"""
        if self.selected_curation_index < len(self.curation_history):
            history_entry = self.curation_history[self.selected_curation_index]
            curator = history_entry.get("curator", "Unknown")
            timestamp = history_entry.get("timestamp", "")
            if "." in timestamp:
                timestamp = timestamp.split(".")[0]
            curator_time = f"**Curator:** {curator} | **Time:** {timestamp}"
            self.metadata_pane.object = curator_time
        else:
            curation_label = f"**Curation {self.selected_curation_index}**"
            self.metadata_pane.object = curation_label

    def _process_ephys_url(self, reference: str) -> str:
        """Process ephys GUI URL by decoding and replacing placeholders"""
        if not reference:
            return ""

        print(reference)

        processed = unquote(reference)

        print(processed)
        if "{derived_asset_location}" in processed:
            derived_loc = f"s3://{self.bucket}/{self.prefix}"
            processed = processed.replace("{derived_asset_location}", derived_loc)
        if "{raw_asset_location}" in processed and self.raw_s3_loc:
            raw_loc = f"s3://{self.raw_s3_loc.lstrip('s3://')}"
            processed = processed.replace("{raw_asset_location}", raw_loc)

        print(processed)

        return processed

    def _send_curation_to_iframe(self):
        """Send curation data to iframe by updating the reactive parameter"""
        if self.iframe_component:
            self.iframe_component.curation_message = self.data

    def set_submit_dirty(self):
        """Mark that there are pending changes to submit"""
        print("EphysCuration: Changes detected from interactive media")

    def __panel__(self):
        """Return the panel representation of this component"""
        return self.content
