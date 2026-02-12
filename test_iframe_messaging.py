"""Test Panel app for debugging iframe message communication

This app creates two iframes and demonstrates bidirectional message passing
between the Panel app and the iframes.

Run with: panel serve test_iframe_messaging.py --show
"""

import panel as pn
import param
from panel.reactive import ReactiveHTML

pn.extension()


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


class IframeMessageTester(pn.viewable.Viewer):
    """Test component for iframe message communication"""

    message_log = param.List(default=[])
    message_to_send = param.String(default="")
    target_iframe = param.Selector(default="iframe1", objects=["iframe1", "iframe2"])

    def __init__(self, **params):
        super().__init__(**params)
        
        # Create message receiver that forwards messages to Python
        self.receiver = MessageReceiver()
        self.receiver.param.watch(self._on_message_received, 'received_message')
        
        # Create two test iframes
        self.iframe1 = self._create_iframe("iframe1", "#FF6B6B", "Iframe 1")
        self.iframe2 = self._create_iframe("iframe2", "#4ECDC4", "Iframe 2")
        
        # Create controls
        self.message_input = pn.widgets.TextInput(
            name="Message to Send",
            placeholder="Enter message...",
            value=""
        )
        self.target_selector = pn.widgets.RadioButtonGroup(
            name="Target Iframe",
            options=["iframe1", "iframe2"],
            value="iframe1",
            button_type="primary"
        )
        self.send_button = pn.widgets.Button(
            name="Send Message",
            button_type="success"
        )
        self.send_button.on_click(self._send_message)
        
        # Create log display
        self.log_display = pn.pane.Markdown(
            "### Message Log\n\nWaiting for messages...\n\n",
            sizing_mode="stretch_both"
        )
        
        # Create message sender component
        self.message_sender = self._create_message_sender()
    
    def _on_message_received(self, event):
        """Handle messages received from iframes"""
        message_data = event.new
        if not message_data or not message_data.get('data'):
            return
        
        data = message_data['data']
        timestamp = message_data.get('timestamp', '')
        source = data.get('source', 'unknown')
        
        # Format the log entry with better JSON formatting
        import json
        data_str = json.dumps(data, indent=2)
        log_entry = f"**[{timestamp[:19]}] 📥 From `{source}`:**\n```json\n{data_str}\n```\n\n"
        
        # Update log display
        current_log = self.log_display.object
        if "Waiting for messages..." in current_log:
            self.log_display.object = "### Message Log\n\n" + log_entry
        else:
            self.log_display.object = current_log + log_entry
        
        print(f"[Python] Received message from {source}: {data}")

    def _create_iframe(self, iframe_id: str, color: str, title: str) -> pn.pane.HTML:
        """Create an iframe with embedded JavaScript for message handling"""
        
        html_content = f"""
        <div style="width: 100%; height: 100%; border: 3px solid {color}; border-radius: 8px; overflow: hidden;">
            <iframe id="{iframe_id}" 
                    srcdoc='
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            body {{
                                margin: 0;
                                padding: 20px;
                                font-family: Arial, sans-serif;
                                background: linear-gradient(135deg, {color}22, {color}44);
                                height: 100vh;
                                display: flex;
                                flex-direction: column;
                                gap: 10px;
                            }}
                            .header {{
                                font-size: 24px;
                                font-weight: bold;
                                color: {color};
                                margin-bottom: 10px;
                            }}
                            .log {{
                                background: white;
                                border: 2px solid {color};
                                border-radius: 4px;
                                padding: 10px;
                                flex: 1;
                                overflow-y: auto;
                                font-family: monospace;
                                font-size: 12px;
                            }}
                            button {{
                                background: {color};
                                color: white;
                                border: none;
                                padding: 10px 20px;
                                border-radius: 4px;
                                cursor: pointer;
                                font-size: 14px;
                                font-weight: bold;
                            }}
                            button:hover {{
                                opacity: 0.8;
                            }}
                            .message-entry {{
                                padding: 5px;
                                border-bottom: 1px solid #eee;
                            }}
                            .timestamp {{
                                color: #666;
                                font-size: 10px;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="header">{title} 🖼️</div>
                        <button onclick="sendTestMessage()">Send Test Message to Parent</button>
                        <div class="log" id="messageLog">
                            <div class="message-entry">
                                <span class="timestamp">[Ready]</span> Waiting for messages...
                            </div>
                        </div>
                        
                        <script>
                            const iframeId = "{iframe_id}";
                            const log = document.getElementById("messageLog");
                            
                            function addLogEntry(message, type = "info") {{
                                const timestamp = new Date().toLocaleTimeString();
                                const entry = document.createElement("div");
                                entry.className = "message-entry";
                                entry.innerHTML = `
                                    <span class="timestamp">[${{timestamp}}]</span>
                                    <strong>[${{type}}]</strong> ${{JSON.stringify(message)}}
                                `;
                                log.appendChild(entry);
                                log.scrollTop = log.scrollHeight;
                            }}
                            
                            function sendTestMessage() {{
                                const message = {{
                                    source: iframeId,
                                    timestamp: new Date().toISOString(),
                                    data: {{
                                        test: "Hello from " + iframeId,
                                        random: Math.random()
                                    }}
                                }};
                                
                                console.log("[" + iframeId + "] Sending message:", message);
                                window.parent.postMessage(message, "*");
                                addLogEntry(message, "SENT");
                            }}
                            
                            // Listen for messages from parent
                            window.addEventListener("message", (event) => {{
                                console.log("[" + iframeId + "] Received message:", event.data);
                                addLogEntry(event.data, "RECEIVED");
                            }});
                            
                            console.log("[" + iframeId + "] Iframe initialized and listening");
                        </script>
                    </body>
                    </html>'
                    style="width: 100%; height: 450px; border: none;">
            </iframe>
        </div>
        """
        
        return pn.pane.HTML(html_content, sizing_mode="stretch_width", height=500)

    def _create_message_sender(self) -> pn.pane.HTML:
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

    def _send_message(self, event):
        """Send a message to the selected iframe"""
        message = self.message_input.value
        target = self.target_selector.value
        
        if not message:
            return
        
        # Log the action
        from datetime import datetime
        import json
        
        timestamp = datetime.now().isoformat()
        message_obj = {"text": message, "from": "panel_app"}
        message_str = json.dumps(message_obj, indent=2)
        log_entry = f"**[{timestamp[:19]}] 📤 Sent to `{target}`:**\n```json\n{message_str}\n```\n\n"
        
        current_log = self.log_display.object
        if "Waiting for messages..." in current_log:
            self.log_display.object = "### Message Log\n\n" + log_entry
        else:
            self.log_display.object = current_log + log_entry
        
        # Create JS execution pane to send message
        js_code = f"""
        <script>
        (function() {{
            const message = {{"text": "{message}", "from": "panel_app"}};
            if (window.sendMessageToIframe) {{
                window.sendMessageToIframe('{target}', message);
            }} else {{
                console.error('sendMessageToIframe not available');
            }}
        }})();
        </script>
        """
        
        # Execute by creating a temporary HTML pane
        temp_sender = pn.pane.HTML(js_code, sizing_mode="fixed", width=0, height=0)
        self._layout.append(temp_sender)
        
        # Clear input
        self.message_input.value = ""

    def __panel__(self):
        """Return the panel layout"""
        
        info_card = pn.pane.Markdown("""
        ## 🧪 Iframe Message Testing App
        
        **Instructions:**
        1. Click buttons inside the iframes to send messages to the parent (check log below)
        2. Use the controls below to send messages to the iframes
        3. Open browser console (F12) to see detailed message logs
        4. Check `window.receivedMessages` for all received messages
        
        **What to test:**
        - Messages from iframe → parent (click buttons in iframes) - 📥 shown in log
        - Messages from parent → iframe (use controls below) - 📤 shown in log  
        - Message format and data structure
        - Cross-iframe communication patterns
        
        **Message Flow:**
        - 📥 Received messages appear in the log below in real-time
        - 📤 Sent messages are logged immediately
        - All messages also logged to browser console
        """, sizing_mode="stretch_width")
        
        controls_card = pn.Card(
            pn.Row(
                self.message_input,
                self.target_selector,
                self.send_button,
            ),
            title="📤 Send Message to Iframe",
            collapsed=False,
        )
        
        log_card = pn.Card(
            self.log_display,
            title="📋 Message Log",
            collapsed=False,
            sizing_mode="stretch_both",
            height=200,
        )
        
        self._layout = pn.Column(
            info_card,
            controls_card,
            pn.Row(
                self.iframe1,
                self.iframe2,
            ),
            log_card,
            self.receiver,
            self.message_sender,
            sizing_mode="stretch_width",
        )
        
        return self._layout


# Create the app
app = IframeMessageTester()

# Serve as a template
template = pn.template.FastListTemplate(
    title="Iframe Message Testing",
    main=[app],
    main_max_width="1800px",
)

template.servable()
