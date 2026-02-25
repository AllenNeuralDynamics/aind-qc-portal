"""Generic curation panel for displaying curation data with media references"""

import json
from urllib.parse import quote, unquote
from uuid import uuid4

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent, ReactComponent

from aind_qc_portal.view_contents.panels.media.media import Media
from aind_qc_portal.view_contents.panels.media.utils import Fullscreen

DEBUG_EPHYS = False
EPHYS_LOCALPORT = 5010


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

        self.identifier = str(uuid4())

        self._init_panel_objects()

        self._populate_data(data)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.dropdown = pn.widgets.Select.from_param(self.param.selected_key, name="Curation Key", options=[])
        self.table = pn.pane.DataFrame()

        if self.has_references:
            self.media = pn.Column()
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


class EphysCurationListener(ReactComponent):
    """
    Listens on the *parent* window for postMessage events of type ``curation-data``
    sent by the embedded ephys_gui_app iframes and forwards them to Python.
    """

    accept_type = param.String(default="curation-data")
    identifier = param.String(default="")

    _esm = """
    export function render({ model }) {
      const [acceptType] = model.useState("accept_type");
      const [identifier] = model.useState("identifier");

      function onMessage(event) {
        const data = event.data;
        if (!data || data.source === "react-devtools-content-script") return;
        if (acceptType && data.type !== acceptType) return;
        if (identifier && data.identifier !== identifier) return;
        model.send_msg({ payload: data, _ts: Date.now() });
      }

      React.useEffect(() => {
        window.addEventListener("message", onMessage);
        return () => window.removeEventListener("message", onMessage);
      }, [acceptType, identifier]);

      return <></>;
    }
    """


class EphysPostMessageSender(ReactComponent):
    """
    Invisible component that, whenever *message_json* changes, posts a
    ``curation-data`` message into all iframes (including Shadow DOMs) on the page.
    """

    message_json = param.String(default="")

    _esm = """
    export function render({ model }) {
      const [messageJson] = model.useState("message_json");

      function findIframes(root) {
        const results = [];
        // Direct iframes under this root
        root.querySelectorAll("iframe").forEach((el) => results.push(el));
        // Recurse into shadow roots
        root.querySelectorAll("*").forEach((el) => {
          if (el.shadowRoot) {
            findIframes(el.shadowRoot).forEach((f) => results.push(f));
          }
        });
        return results;
      }

      React.useEffect(() => {
        if (!messageJson) return;

        try {
          const parsed = JSON.parse(messageJson);
          const iframes = findIframes(document);
          iframes.forEach((iframe) => {
            if (iframe.contentWindow) {
              iframe.contentWindow.postMessage(parsed, "*");
              console.log(`[parent] Sent to iframe#${iframe.id || '(no id)'}:`, parsed);
            }
          });
          if (iframes.length === 0) {
            console.warn("[parent] No iframes found on the page (including shadow DOMs)");
          }
        } catch (err) {
          console.error("[parent] JSON parse error:", err);
        }
      }, [messageJson]);

      return <></>;
    }
    """


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

        self.identifier = str(uuid4())

        self.curation_values = curation_values or [data]
        self.curation_history = curation_history or {}
        self.data = self.curation_values[-1] if self.curation_values else data
        self.iframe_component = None
        self._init_panel_objects()

    def _init_panel_objects(self):
        """Initialize panel objects"""
        self.json_editor = pn.pane.JSON(
            object=self.data,
        )

        curation_options = self._build_curation_options()
        self.curation_dropdown = pn.widgets.Select.from_param(
            self.param.selected_curation_index, name="Select Curation", options=curation_options
        )
        self.send_button = pn.widgets.Button(name="Send curation", button_type="primary", sizing_mode="stretch_width")
        self.send_button.on_click(self._send_curation_to_iframe)

        self.metadata_pane = pn.pane.Markdown("", sizing_mode="stretch_width")
        self._update_metadata_display()

        processed_url = self._process_ephys_url(self.reference)
        print(f"EphysCuration: Processed ephys GUI URL: {processed_url}")
        self.iframe_component = pn.pane.HTML(
            f'<iframe id="iframe-0000" src="{processed_url}" '
            f'style="width:100%;height:100%;border: none;" '
            f'allow="cross-origin-isolated"></iframe>',
            width=1200,
            height=900,
            sizing_mode="fixed",
        )
        fullscreen_iframe = Fullscreen(self.iframe_component)

        self.ephys_sender = EphysPostMessageSender()
        self.ephys_listener = EphysCurationListener(identifier=self.identifier)
        self.ephys_listener.on_msg(self._on_curation_received)

        self.content = pn.Row(
            pn.Column(
                self.curation_dropdown,
                self.metadata_pane,
                self.json_editor,
                self.send_button,
                self.ephys_sender,
                self.ephys_listener,
                max_width=350,
            ),
            pn.Column(
                fullscreen_iframe,
                width=1200,
            ),
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

    def _on_curation_received(self, msg):
        """Handle curation data received from iframe"""
        data = msg.data
        payload = data.get("payload", {})
        if payload.get("type") != "curation-data":
            print(f"EphysCuration: Ignoring message with unsupported type: {payload.get('type')}")
            return
        if payload.get("identifier") != self.identifier:
            print(f"EphysCuration: Ignoring message with mismatched identifier: {payload.get('identifier')}")
            return
        data = payload.get("data", {})
        identifier = payload.get("identifier", "???")
        print(f"EphysCuration: Received message from iframe (identifier: {identifier})")

        if self.value_callback:
            self.value_callback(data)

    def _process_ephys_url(self, reference: str) -> str:
        """Process ephys GUI URL by decoding and replacing placeholders"""
        if not reference:
            return ""

        processed = unquote(reference)
        if DEBUG_EPHYS:
            processed = processed.replace(
                "https://ephys.allenneuraldynamics.org", f"http://localhost:{EPHYS_LOCALPORT}"
            )
        processed += f"&identifier={self.identifier}&fast_mode=true"
        print(f"EphysCuration: Decoded ephys GUI URL: {processed}")

        if "{derived_asset_location}" in processed:
            derived_loc = f"s3://{self.bucket}/{self.prefix}"
            processed = processed.replace("{derived_asset_location}", derived_loc)
        if "{raw_asset_location}" in processed and self.raw_s3_loc:
            raw_loc = f"s3://{self.raw_s3_loc.lstrip('s3://')}"
            processed = processed.replace("{raw_asset_location}", raw_loc)

        processed = quote(processed, safe=":/?&=-")

        return processed

    def _send_curation_to_iframe(self, event):
        """Build a curation-data postMessage payload and push it into the sender."""
        identifier = self.identifier

        if len(self.data) == 0:
            curation_data = {}
        else:
            curation_data = self.data

        envelope = {
            "type": "curation-data",
            "identifier": identifier,
            "data": curation_data,
        }
        print(f"EphysCuration: Sending curation data to iframe (identifier: {identifier})")

        # Append a unique counter so the param change always fires
        self.ephys_sender.message_json = json.dumps(envelope)

    def __panel__(self):
        """Return the panel representation of this component"""
        return self.content
