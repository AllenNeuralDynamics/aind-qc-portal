"""Generic curation panel for displaying curation data with media references"""

import json
import uuid
from urllib.parse import quote, unquote

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent
from panel.reactive import ReactiveHTML

from aind_qc_portal.view_contents.panels.media.media import Media
from aind_qc_portal.view_contents.panels.media.utils import Fullscreen

_EPHYS_CURATION_REGISTRY: dict[str, "EphysCuration"] = {}


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


class MessageReceiver(ReactiveHTML):
    """ReactiveHTML component that receives postMessage events and forwards to Python"""
    
    received_message = param.Dict(default={})
    
    _template = """
    <div id="receiver" style="display: none;"></div>
    """
    
    _scripts = {
        "render": """
            console.log('[MessageReceiver] Initializing...');
            
            const handler = (event) => {
                console.log('=== [MessageReceiver] MESSAGE RECEIVED ===');
                console.log('[MessageReceiver] Origin:', event.origin);
                console.log('[MessageReceiver] Data:', event.data);
                
                // Store for inspection
                if (!window.receivedMessages) {
                    window.receivedMessages = [];
                }
                window.receivedMessages.push({
                    timestamp: new Date().toISOString(),
                    origin: event.origin,
                    data: event.data
                });
                
                // Forward to Python via parameter update
                if (event.data && typeof event.data === 'object') {
                    const message = {
                        timestamp: new Date().toISOString(),
                        origin: event.origin,
                        data: event.data
                    };
                    data.received_message = message;
                    console.log('[MessageReceiver] Forwarded to Python:', message);
                }
            };
            
            window.addEventListener('message', handler);
            console.log('[MessageReceiver] Listener attached');
        """
    }


def _create_ephys_iframe_html(iframe_id: str, src: str) -> pn.pane.HTML:
    """Create an iframe HTML pane with a unique ID.

    Parameters
    ----------
    iframe_id : str
        Unique identifier for this iframe
    src : str
        The URL to load in the iframe
    """
    html_content = f"""
    <div style="width: 100%; height: 100%;">
        <iframe id="{iframe_id}"
                src="{src}"
                style="width: 100%; height: 100%; border: none;">
        </iframe>
    </div>
    """
    return pn.pane.HTML(html_content, sizing_mode="fixed", width=1200, height=900)


def _create_message_sender() -> pn.pane.HTML:
    """Create a component that can send messages to iframes"""
    
    html_content = """
    <div id="message_sender"></div>
    <script>
    // Function to find iframe in regular DOM and shadow DOM
    function findIframe(iframeId, root = document) {
        // Try regular DOM first
        let iframe = root.getElementById(iframeId);
        if (iframe) return iframe;
        
        // Search through shadow roots
        const allElements = root.querySelectorAll('*');
        for (let el of allElements) {
            if (el.shadowRoot) {
                iframe = findIframe(iframeId, el.shadowRoot);
                if (iframe) return iframe;
            }
        }
        
        return null;
    }
    
    window.sendMessageToIframe = function(iframeId, message) {
        console.log('[MessageSender] Sending to', iframeId, ':', message);
        console.log('[MessageSender] Searching DOM and shadow roots...');
        
        const iframe = findIframe(iframeId);
        if (iframe) {
            console.log('[MessageSender] Found iframe:', iframe);
            
            if (iframe.contentWindow) {
                const fullMessage = {
                    source: 'parent',
                    timestamp: new Date().toISOString(),
                    payload: message
                };
                
                iframe.contentWindow.postMessage(fullMessage, '*');
                console.log('[MessageSender] Message sent successfully');
                return true;
            } else {
                console.error('[MessageSender] Iframe has no contentWindow');
                return false;
            }
        } else {
            console.error('[MessageSender] Could not find iframe:', iframeId);
            console.log('[MessageSender] Available iframes in document:');
            document.querySelectorAll('iframe').forEach(f => console.log('  -', f.id || '(no id)', f));
            return false;
        }
    };
    
    console.log('[MessageSender] Ready. Use window.sendMessageToIframe(iframeId, message)');
    </script>
    """
    
    return pn.pane.HTML(html_content, sizing_mode="fixed", width=0, height=0)


class EphysCuration(PyComponent):
    """Ephys/Spike sorting curation panel"""

    selected_curation_index = param.Integer(default=0)

    _message_receiver = None  # shared across all instances

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

        self.iframe_id = f"ephys_iframe_{uuid.uuid4().hex[:12]}"
        _EPHYS_CURATION_REGISTRY[self.iframe_id] = self

        if EphysCuration._message_receiver is None:
            print("[EphysCuration.__init__] Creating shared MessageReceiver")
            EphysCuration._message_receiver = MessageReceiver()
            EphysCuration._message_receiver.param.watch(
                EphysCuration._dispatch_message, "received_message"
            )
            print("[EphysCuration.__init__] MessageReceiver created and watcher attached")
        else:
            print("[EphysCuration.__init__] Using existing shared MessageReceiver")

        self._init_panel_objects()

    @staticmethod
    def _dispatch_message(event):
        """Route an incoming message to the correct EphysCuration instance"""
        print("[EphysCuration._dispatch_message] Called!")
        print(f"[EphysCuration._dispatch_message] event.new type: {type(event.new)}")
        print(f"[EphysCuration._dispatch_message] event.new: {event.new}")
        
        message_data = event.new
        if not message_data:
            print("[EphysCuration._dispatch_message] No message_data, returning")
            return
            
        if not message_data.get('data'):
            print(f"[EphysCuration._dispatch_message] No 'data' key in message_data. Keys: {list(message_data.keys())}")
            return
        
        data = message_data['data']
        print(f"[EphysCuration._dispatch_message] Extracted data: {data}")
        print(f"[EphysCuration._dispatch_message] Data type: {type(data)}")
        
        source = data.get('source', 'unknown')
        print(f"[EphysCuration._dispatch_message] Message source: {source}")
        print(f"[EphysCuration._dispatch_message] Registry keys: {list(_EPHYS_CURATION_REGISTRY.keys())}")
        
        # Look up the instance by iframe_id
        instance = _EPHYS_CURATION_REGISTRY.get(source)
        
        # Fallback: if source is unknown/parent and there's only one instance, use it
        if not instance and source in ('unknown', 'parent') and len(_EPHYS_CURATION_REGISTRY) == 1:
            instance = list(_EPHYS_CURATION_REGISTRY.values())[0]
            print(f"[EphysCuration._dispatch_message] Using fallback - single instance: {instance.iframe_id}")
        
        if instance:
            print(f"[EphysCuration._dispatch_message] Found instance for source={source}")
            # Extract curation data from the payload
            if data.get('payload') and isinstance(data['payload'], dict):
                print("[EphysCuration._dispatch_message] Found payload in data")
                if data['payload'].get('type') == 'curation-data':
                    curation_data = data['payload'].get('data')
                    print(f"[EphysCuration._dispatch_message] Extracted curation-data: {curation_data}")
                else:
                    curation_data = data['payload']
                    print(f"[EphysCuration._dispatch_message] Using full payload: {curation_data}")
            else:
                curation_data = data
                print(f"[EphysCuration._dispatch_message] Using raw data: {curation_data}")
            
            if curation_data:
                print(f"[EphysCuration._dispatch_message] Calling _on_message_received with: {curation_data}")
                instance._on_message_received(curation_data)
            else:
                print("[EphysCuration._dispatch_message] curation_data is empty/None!")
        else:
            print(f"[EphysCuration._dispatch_message] No instance registered for source={source}")
            print(f"[EphysCuration._dispatch_message] Available instances: {list(_EPHYS_CURATION_REGISTRY.keys())}")

    def _on_message_received(self, curation_data: dict):
        """Handle curation data received from the iframe"""
        print("=" * 80)
        print(f"[EphysCuration._on_message_received] IFRAME {self.iframe_id} RECEIVED DATA")
        print(f"[EphysCuration._on_message_received] Curation data type: {type(curation_data)}")
        print(f"[EphysCuration._on_message_received] Curation data: {curation_data}")
        
        self.data = curation_data
        self.json_editor.object = self.data
        print(f"[EphysCuration._on_message_received] Updated JSON editor")
        
        if self.value_callback:
            print(f"[EphysCuration._on_message_received] Calling value_callback")
            self.value_callback(curation_data)
            print(f"[EphysCuration._on_message_received] value_callback completed")
        else:
            print(f"[EphysCuration._on_message_received] No value_callback set!")
        print("=" * 80)

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

        processed_url = self._process_ephys_url(self.reference)

        self.iframe_pane = _create_ephys_iframe_html(self.iframe_id, processed_url)
        fullscreen_iframe = Fullscreen(self.iframe_pane)

        self._sender_column = pn.Column(sizing_mode="fixed", width=0, height=0)

        # Only add the shared components to the first instance's layout
        right_column_items = [fullscreen_iframe, self._sender_column]
        if len(_EPHYS_CURATION_REGISTRY) == 1:
            print(f"[EphysCuration._init_panel_objects] First instance - adding shared components")
            print(f"[EphysCuration._init_panel_objects] Adding message sender and receiver to layout")
            right_column_items.append(_create_message_sender())
            right_column_items.append(EphysCuration._message_receiver)
        else:
            print(f"[EphysCuration._init_panel_objects] Not first instance - using shared components from first instance")
            print(f"[EphysCuration._init_panel_objects] Registry has {len(_EPHYS_CURATION_REGISTRY)} instances")

        self.content = pn.Row(
            pn.Column(
                self.curation_dropdown,
                self.metadata_pane,
                self.json_editor,
                max_width=350,
            ),
            pn.Column(
                *right_column_items,
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

    def _process_ephys_url(self, reference: str) -> str:
        """Process ephys GUI URL by decoding and replacing placeholders"""
        if not reference:
            return ""

        processed = unquote(reference)

        if "{derived_asset_location}" in processed:
            derived_loc = f"s3://{self.bucket}/{self.prefix}"
            processed = processed.replace("{derived_asset_location}", derived_loc)
        if "{raw_asset_location}" in processed and self.raw_s3_loc:
            raw_loc = f"s3://{self.raw_s3_loc.lstrip('s3://')}"
            processed = processed.replace("{raw_asset_location}", raw_loc)

        processed = quote(processed, safe=":/?&=")

        return processed

    def _send_curation_to_iframe(self):
        """Send curation data to the iframe via window.sendMessageToIframe"""
        print(f"[EphysCuration._send_curation_to_iframe] Sending to iframe {self.iframe_id}")
        print(f"[EphysCuration._send_curation_to_iframe] Data: {self.data}")
        
        data_json = json.dumps(self.data)
        js_code = f"""
        <script>
        (function() {{
            console.log('[_send_curation_to_iframe] Script executing');
            const message = {data_json};
            console.log('[_send_curation_to_iframe] Message to send:', message);
            console.log('[_send_curation_to_iframe] Target iframe:', '{self.iframe_id}');
            if (window.sendMessageToIframe) {{
                console.log('[_send_curation_to_iframe] Calling window.sendMessageToIframe');
                window.sendMessageToIframe('{self.iframe_id}', message);
            }} else {{
                console.error('[_send_curation_to_iframe] sendMessageToIframe not available!');
                console.log('[_send_curation_to_iframe] window keys:', Object.keys(window));
            }}
        }})();
        </script>
        """
        
        temp_sender = pn.pane.HTML(js_code, sizing_mode="fixed", width=0, height=0)
        self._sender_column.clear()
        self._sender_column.append(temp_sender)
        print(f"[EphysCuration._send_curation_to_iframe] Temp sender appended to column")

    def __panel__(self):
        """Return the panel representation of this component"""
        return self.content
