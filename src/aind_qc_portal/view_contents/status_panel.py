"""Minimal status page Panel app for AIND QC Portal health checks."""

import panel as pn
import requests

STATUS_ENDPOINT = "/status"

CHECK_ICONS = {
    "success": "✅",
    "error": "❌",
    "pending": "⏳",
}

CHECK_LABELS = {
    "docdb_load": "Load QC from DocDB",
    "docdb_roundtrip": "DocDB read/write roundtrip",
    # Add more as implemented
}

def fetch_status():
    try:
        resp = requests.get(STATUS_ENDPOINT)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

class StatusPanel:
    def __init__(self):
        self.status = pn.pane.Markdown("Loading status checks...", sizing_mode="stretch_width")
        self.refresh_button = pn.widgets.Button(name="Refresh", button_type="primary")
        self.refresh_button.on_click(self.update_status)
        self.panel = pn.Column(
            pn.pane.Markdown("# QC Portal Status", sizing_mode="stretch_width"),
            self.status,
            self.refresh_button,
            sizing_mode="stretch_width",
            width=400,
        )
        self.update_status()

    def update_status(self, *_):
        results = fetch_status()
        if "status" in results and results["status"] == "error":
            self.status.object = f"**Error:** {results.get('error', 'Unknown error')}"
            return
        lines = []
        for key, label in CHECK_LABELS.items():
            check = results.get(key, {})
            icon = CHECK_ICONS.get(check.get("status", "pending"), CHECK_ICONS["pending"])
            lines.append(f"{icon} {label}")
        self.status.object = "\n".join(lines)

    def __panel__(self):
        return self.panel

status_panel = StatusPanel()

if __name__.startswith("bokeh"):  # For panel serve
    pn.extension()
    status_panel.panel.servable()
