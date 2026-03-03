"""
Status panel UI for AIND QC Portal health checks.
"""

import panel as pn

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.status_contents.checks import run_all_status_checks

# Labels for checks
CHECK_LABELS = {
    "docdb_load": "Load QC from DocDB",
    "s3_media_access": "S3 Media Access",
    "zombie_squirrel": "Zombie Squirrel Access",
}


class StatusPanel:
    """Panel UI for displaying system status checks."""

    def __init__(self):
        """Initialize the status panel UI."""

        self.title = pn.pane.HTML("<h1 style='text-align: center;'>QC Portal System Status</h1>")
        self.overall_status = pn.pane.Markdown("Click Refresh to check system status.")

        self.docdb_status = pn.widgets.StaticText(name="DocDB Status", value="Not checked")
        self.s3_status = pn.widgets.StaticText(name="S3 Status", value="Not checked")
        self.zombie_status = pn.widgets.StaticText(name="Zombie Squirrel Status", value="Not checked")

        self.refresh_button = pn.widgets.Button(name="Refresh", button_type="primary")
        self.refresh_button.on_click(self.update_status)

        # Create main panel structure
        self.content_panel = pn.Column(
            self.title,
            self.overall_status,
            pn.Spacer(height=20),
            self.docdb_status,
            self.s3_status,
            self.zombie_status,
            pn.Spacer(height=20),
            pn.Row(pn.HSpacer(), self.refresh_button, pn.HSpacer()),
            styles=OUTER_STYLE,
            sizing_mode="stretch_width",
        )

        self.panel = pn.Row(
            pn.HSpacer(),
            pn.Column(
                pn.VSpacer(height=20), self.content_panel, pn.VSpacer(), sizing_mode="stretch_width", max_width=800
            ),
            pn.HSpacer(),
            sizing_mode="stretch_width",
        )

    def update_status(self, *_):
        """Update the status display with current check results."""

        self.overall_status.object = "⏳ Checking system status..."
        self.docdb_status.value = "⏳ Checking..."
        self.s3_status.value = "⏳ Checking..."
        self.zombie_status.value = "⏳ Checking..."

        try:
            results = run_all_status_checks()

            # Update individual status displays
            docdb_result = results.get("docdb_load", {})
            if isinstance(docdb_result, dict) and docdb_result:
                # Multiple assets
                success_count = sum(1 for r in docdb_result.values() if r.get("status") == "success")
                total_count = len(docdb_result)
                if success_count == total_count:
                    self.docdb_status.value = f"✅ All {total_count} assets loaded successfully"
                else:
                    self.docdb_status.value = f"❌ {success_count}/{total_count} assets loaded successfully"
            else:
                self.docdb_status.value = "❌ Failed to check DocDB"

            s3_result = results.get("s3_media_access", {})
            if isinstance(s3_result, dict) and s3_result:
                # Multiple assets
                success_count = sum(1 for r in s3_result.values() if r.get("status") == "success")
                total_count = len(s3_result)
                if success_count == total_count:
                    self.s3_status.value = f"✅ All {total_count} assets accessible in S3"
                else:
                    self.s3_status.value = f"❌ {success_count}/{total_count} assets accessible in S3"
            else:
                self.s3_status.value = "❌ Failed to check S3"

            zombie_result = results.get("zombie_squirrel", {})
            if zombie_result.get("status") == "success":
                projects = zombie_result.get("num_projects", 0)
                assets = zombie_result.get("num_assets", 0)
                self.zombie_status.value = f"✅ Connected ({projects} projects, {assets} assets)"
            else:
                error_msg = zombie_result.get("error", "Unknown error")
                self.zombie_status.value = f"❌ Failed: {error_msg}"

            # Update overall status
            all_good = (
                "✅" in self.docdb_status.value and "✅" in self.s3_status.value and "✅" in self.zombie_status.value
            )

            if all_good:
                self.overall_status.object = "## ✅ All Systems Operational"
            else:
                self.overall_status.object = "## ❌ Some Systems Have Issues"

        except Exception as e:
            self.overall_status.object = f"## ❌ Error checking status: {str(e)}"
            self.docdb_status.value = "❌ Error during check"
            self.s3_status.value = "❌ Error during check"
            self.zombie_status.value = "❌ Error during check"

    def __panel__(self):
        """Return the panel object for display."""
        return self.panel
