"""Generic curation panel for displaying curation data with media references"""

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent

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

    selected_curation_index = param.Integer(default=0)

    def __init__(self, data: dict, bucket, prefix, raw_s3_loc=None, reference=None, value_callback=None, curation_values=None, curation_history=None):
        """Initialize EphysCuration panel
        
        Parameters
        ----------
        data : dict
            Current curation data (deprecated, use curation_values instead)
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
        self.iframe_ref = None

        self._init_panel_objects()
        self._send_curation_to_iframe()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.json_editor = pn.pane.JSON(
            object=self.data,
        )

        curation_options = self._build_curation_options()
        self.curation_dropdown = pn.widgets.Select.from_param(
            self.param.selected_curation_index, 
            name="Select Curation", 
            options=curation_options
        )
        self.param.watch(self._on_curation_selection_change, "selected_curation_index")

        # Metadata display for selected curation
        self.metadata_pane = pn.pane.Markdown("", sizing_mode="stretch_width")
        self._update_metadata_display()

        # Initialize reusable script pane for iframe messaging
        self.script_pane = pn.pane.HTML("", sizing_mode="stretch_width", height=0)

        if self.reference:
            media_panel = Media(
                reference=self.reference,
                s3_bucket=self.bucket,
                s3_prefix=self.prefix,
                raw_s3_loc=self.raw_s3_loc,
                lazy_load=False,
                value_callback=self._value_callback_wrapper,
                parent=self,
            )
            self.iframe_ref = media_panel
            self.iframe_src = self.reference
            self.content = pn.Row(
                pn.Column(
                    self.curation_dropdown,
                    self.metadata_pane,
                    self.json_editor,
                    self.script_pane,
                ),
                media_panel,
            )
        else:
            self.content = pn.Column(
                self.curation_dropdown,
                self.metadata_pane,
                self.json_editor,
                self.script_pane,
            )

    def _build_curation_options(self):
        """Build dropdown options from curation history"""
        options = {}
        for i in range(len(self.curation_values)):
            if i < len(self.curation_history):
                history_entry = self.curation_history[i]
                curator = history_entry.get("curator", "Unknown")
                timestamp = history_entry.get("timestamp", "")
                # Truncate milliseconds from timestamp
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
        """Update the metadata display for the currently selected curation"""
        if self.selected_curation_index < len(self.curation_history):
            history_entry = self.curation_history[self.selected_curation_index]
            curator = history_entry.get("curator", "Unknown")
            timestamp = history_entry.get("timestamp", "")
            # Truncate milliseconds from timestamp
            if "." in timestamp:
                timestamp = timestamp.split(".")[0]
            self.metadata_pane.object = f"**Curator:** {curator} | **Time:** {timestamp}"
        else:
            self.metadata_pane.object = f"**Curation {self.selected_curation_index}**"

    def _send_curation_to_iframe(self):
        """Send curation data to iframe via postMessage"""
        if self.iframe_ref is None or not hasattr(self, 'iframe_src'):
            return
        
        import json
        
        curation_message = {
            "payload": {
                "type": "curation-data",
                "data": self.data
            }
        }
        
        message_json = json.dumps(curation_message)
        iframe_src_json = json.dumps(self.iframe_src)
        
        # Generate script that traverses shadowDOM to find iframes
        script = f"""
        <script>
        (function() {{
            console.log('[EphysCuration] Attempting to send curation data');
            console.log('[EphysCuration] Target iframe src:', {iframe_src_json});
            console.log('[EphysCuration] Message:', {message_json});
            
            const targetSrc = {iframe_src_json};
            const message = {message_json};
            
            // Function to traverse shadowDOM and find all iframes
            function getAllElementsIncludingShadow(root = document.body) {{
                const elements = [];

                function traverse(node) {{
                    elements.push(node);

                    if (node.shadowRoot) {{
                        traverse(node.shadowRoot);
                    }}

                    for (const child of node.children || []) {{
                        traverse(child);
                    }}
                }}

                traverse(root);
                return elements;
            }}
            
            const allElements = getAllElementsIncludingShadow();
            const iframes = allElements.filter(el => el.tagName === 'IFRAME');
            
            console.log('[EphysCuration] Found', iframes.length, 'iframes');
            
            let messagePosted = false;
            iframes.forEach((iframe, index) => {{
                console.log('[EphysCuration] iframe', index, 'src:', iframe.src);
                if (iframe.src && 
                    iframe.src.includes('ephys.allenneuraldynamics.org')) {{
                    console.log('[EphysCuration] Posting to iframe', index);
                    try {{
                        iframe.contentWindow.postMessage(message, '*');
                        messagePosted = true;
                        console.log('[EphysCuration] Posted successfully');
                    }} catch (e) {{
                        console.error('[EphysCuration] Error:', e);
                    }}
                }}
            }});
            
            if (!messagePosted) {{
                console.warn('[EphysCuration] No matching iframe found');
            }}
        }})();
        </script>
        """
        
        # Update the reusable script pane with new content
        self.script_pane.object = script

    def _value_callback_wrapper(self, new_value):
        """Wrapper to handle value callback from media panel"""

        if isinstance(new_value, dict) and new_value.get("command") == "calculateSubFramePositioning":
            # Ignore positioning commands
            return

        self.data = new_value
        self.json_editor.object = self.data
        
        if self.value_callback:
            self.value_callback(new_value)

    def set_submit_dirty(self):
        """Mark that there are pending changes to submit"""
        # This gets called when interactive media (ephys GUI) updates values
        # The actual submission is handled by the value_callback mechanism
        print("EphysCuration: Changes detected from interactive media")

    def __panel__(self):
        """Return the panel representation of this component"""
        return self.content
