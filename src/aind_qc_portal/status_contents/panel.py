"""
Status panel UI for AIND QC Portal health checks.
"""


import panel as pn

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.status_contents.checks import run_all_status_checks


class StatusMessages:
    """Centralized status messages similar to GitHub Status page."""

    # Icons
    OPERATIONAL_ICON = "✅"
    FAILED_ICON = "❌"
    CHECKING_ICON = "⏳"

    OPERATIONAL = "Operational"
    DEGRADED = "Degraded"
    FAILED = "Failed"
    CHECKING = "Checking"
    UNCHECKED = "Not checked"

    # Overall status messages with styling
    ALL_SYSTEMS_OPERATIONAL = f"<h2 style='color: #28a745; margin: 10px 0;'>{OPERATIONAL_ICON} All Systems Operational</h2>"
    SOME_SYSTEMS_ISSUES = f"<h2 style='color: #dc3545; margin: 10px 0;'>{FAILED_ICON} Some Systems Have Issues</h2>"
    ERROR_DURING_CHECK = f"{FAILED_ICON} Error during check"
    FAILED_TO_CHECK = f"{FAILED_ICON} Failed to check"

    @staticmethod
    def checking_status():
        """Return checking status message."""
        return f"{StatusMessages.CHECKING_ICON} {StatusMessages.CHECKING}"

    @staticmethod
    def operational_with_count(service_name: str, count: int, item_type: str = "assets"):
        """Return operational status with count (GitHub style)."""
        return f"{StatusMessages.OPERATIONAL_ICON} {StatusMessages.OPERATIONAL} ({count} {item_type})"

    @staticmethod
    def degraded_with_count(success: int, total: int, item_type: str = "assets"):
        """Return degraded status with partial success count."""
        return f"{StatusMessages.FAILED_ICON} {StatusMessages.DEGRADED} ({success}/{total} {item_type})"

    @staticmethod
    def failed_with_reason(reason: str = ""):
        """Return failed status with optional reason."""
        if reason:
            return f"{StatusMessages.FAILED_ICON} {StatusMessages.FAILED}: {reason}"
        return f"{StatusMessages.FAILED_ICON} {StatusMessages.FAILED}"

    @staticmethod
    def checking_system_status():
        """Return system-wide checking message."""
        return f"{StatusMessages.CHECKING_ICON} Checking system status..."

    @staticmethod
    def error_checking_status(error: str):
        """Return error message for status check."""
        return f"<h2 style='color: #dc3545; margin: 10px 0;'>{StatusMessages.FAILED_ICON} Error checking status: {error}</h2>"


# Service configurations (like GitHub's service list)
SERVICE_CONFIG = {
    "docdb": {
        "name": "DocDB",
        "description": "Document database connectivity"
    },
    "s3": {
        "name": "S3 Media",
        "description": "S3 storage access"
    },
    "zombie_squirrel": {
        "name": "Zombie Squirrel",
        "description": "Project metadata service"
    }
}


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
        self.overall_status = pn.pane.HTML("Click Refresh to check system status.")

        self.docdb_status = pn.widgets.StaticText(name=SERVICE_CONFIG["docdb"]["name"], value=StatusMessages.UNCHECKED)
        self.s3_status = pn.widgets.StaticText(name=SERVICE_CONFIG["s3"]["name"], value=StatusMessages.UNCHECKED)
        self.zombie_status = pn.widgets.StaticText(name=SERVICE_CONFIG["zombie_squirrel"]["name"], value=StatusMessages.UNCHECKED)

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

    def update_status(self, *_: list):
        """Update the status display with current check results."""

        self.overall_status.object = StatusMessages.checking_system_status()
        self.docdb_status.value = StatusMessages.checking_status()
        self.s3_status.value = StatusMessages.checking_status()
        self.zombie_status.value = StatusMessages.checking_status()

        try:
            results = run_all_status_checks()

            # Update individual status displays
            docdb_result = results.get("docdb_load", {})
            if isinstance(docdb_result, dict) and docdb_result:
                # Multiple assets
                success_count = sum(1 for r in docdb_result.values() if r.get("status") == "success")
                total_count = len(docdb_result)
                if success_count == total_count:
                    self.docdb_status.value = StatusMessages.operational_with_count(
                        SERVICE_CONFIG["docdb"]["name"], total_count
                    )
                else:
                    self.docdb_status.value = StatusMessages.degraded_with_count(success_count, total_count)
            else:
                self.docdb_status.value = StatusMessages.failed_with_reason("Failed to check")

            s3_result = results.get("s3_media_access", {})
            if isinstance(s3_result, dict) and s3_result:
                # Multiple assets
                success_count = sum(1 for r in s3_result.values() if r.get("status") == "success")
                total_count = len(s3_result)
                if success_count == total_count:
                    self.s3_status.value = StatusMessages.operational_with_count(
                        SERVICE_CONFIG["s3"]["name"], total_count
                    )
                else:
                    self.s3_status.value = StatusMessages.degraded_with_count(success_count, total_count)
            else:
                self.s3_status.value = StatusMessages.failed_with_reason("Failed to check")

            zombie_result = results.get("zombie_squirrel", {})
            if zombie_result.get("status") == "success":
                projects = zombie_result.get("num_projects", 0)
                assets = zombie_result.get("num_assets", 0)
                self.zombie_status.value = f"{StatusMessages.OPERATIONAL_ICON} {StatusMessages.OPERATIONAL} ({projects} projects, {assets} assets)"
            else:
                error_msg = zombie_result.get("error", "Connection failed")
                self.zombie_status.value = StatusMessages.failed_with_reason(error_msg)

            # Update overall status (GitHub style)
            all_good = (
                StatusMessages.OPERATIONAL_ICON in self.docdb_status.value and
                StatusMessages.OPERATIONAL_ICON in self.s3_status.value and
                StatusMessages.OPERATIONAL_ICON in self.zombie_status.value
            )

            if all_good:
                self.overall_status.object = StatusMessages.ALL_SYSTEMS_OPERATIONAL
            else:
                self.overall_status.object = StatusMessages.SOME_SYSTEMS_ISSUES

        except Exception as e:
            self.overall_status.object = StatusMessages.error_checking_status(str(e))
            self.docdb_status.value = StatusMessages.ERROR_DURING_CHECK
            self.s3_status.value = StatusMessages.ERROR_DURING_CHECK
            self.zombie_status.value = StatusMessages.ERROR_DURING_CHECK

    def __panel__(self):
        """Return the panel object for display."""
        return self.panel
