"""
Status page Panel app for AIND QC Portal health checks.
Organized to match repo architecture: status logic in status.py, UI in status_panel.py, entrypoint in serve_status.py.
"""

import panel as pn
from aind_qc_portal.status import run_all_status_checks

# Icons and labels for checks
CHECK_ICONS = {
    "success": "✅",
    "error": "❌",
    "pending": "⏳",
}

CHECK_LABELS = {
    "docdb_load": "Load QC from DocDB",
    "s3_media_access": "S3 Media Access",
    "zombie_squirrel": "Zombie Squirrel Access",
    # Add more as implemented
}

class StatusPanel:
    def __init__(self):
        self.status = pn.pane.HTML("Loading status checks...", sizing_mode="stretch_width")
        self.refresh_button = pn.widgets.Button(name="Refresh", button_type="primary")
        self.refresh_button.on_click(self.update_status)
        self.panel = pn.Column(
            self.status,
            self.refresh_button,
            sizing_mode="stretch_width",
            width=500,
        )
        self.update_status()

    def update_status(self, *_):
        results = run_all_status_checks()
        if "status" in results and results["status"] == "error":
            self.status.object = f"<h2 style='color:red;'>❌ Error loading status: {results.get('error', 'Unknown error')}</h2>"
            return

        # Determine overall status
        all_ok = all(results.get(key, {}).get("status") == "success" for key in CHECK_LABELS)
        if all_ok:
            summary = "<h2 style='color:green;'>✅ All Systems Operational</h2>"
        else:
            summary = "<h2 style='color:red;'>❌ Some systems are experiencing issues</h2>"

        # List each check
        lines = []
        for key, label in CHECK_LABELS.items():
            check = results.get(key, {})
            icon = CHECK_ICONS.get(check.get("status", "pending"), CHECK_ICONS["pending"])
            msg = check.get("error", "") if check.get("status") == "error" else ""
            extra = ""
            if check.get("status") == "success" and "num_metrics" in check:
                extra = f"<span style='color:gray;font-size:0.9em;'>({check['num_metrics']} metrics)</span>"
            # Add record and traceback if present (for debugging)
            debug_info = ""
            if check.get("status") == "error":
                if "record" in check:
                    debug_info += f"<br><pre style='color:#b00;font-size:0.9em;'>Record: {check['record']}</pre>"
                if "traceback" in check:
                    debug_info += f"<br><pre style='color:#b00;font-size:0.8em;overflow-x:auto;'>{check['traceback']}</pre>"
            lines.append(f"<div style='font-size:1.2em;'>{icon} {label} {extra} <span style='color:gray;font-size:0.9em;'>{msg}</span>{debug_info}</div>")

        self.status.object = summary + "<br>" + "".join(lines)

    def __panel__(self):
        return self.panel

status_panel = StatusPanel()

if __name__.startswith("bokeh"):  # For panel serve
    pn.extension()
    status_panel.panel.servable()
