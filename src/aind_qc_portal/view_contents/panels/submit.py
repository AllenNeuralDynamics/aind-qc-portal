"""Login and submit panels"""

import pandas as pd
import panel as pn
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.view_contents.data import ViewData


class SubmitPanel(PyComponent):
    """Panel for submitting QC data"""

    def __init__(self, data: ViewData):
        """Initialize SubmitPanel with data"""
        super().__init__()
        self.data = data
        self._init_panel_objects()
        self._init_modal()

    def refresh_page(self):
        """Refresh the page using hidden HTML"""
        self.hidden_html.object = "<script>window.location.reload();</script>"

    def _init_modal(self):
        """Initialize the submission modal dialog"""
        # Status pane for feedback
        self.status_pane = pn.pane.Markdown("")

        # Submit button
        self.upload_button = pn.widgets.Button(
            name="Upload changes",
            button_type="danger",
            disabled=True,
        )

        # Clear changes button
        self.clear_button = pn.widgets.Button(
            name="Clear all changes",
            button_type="warning",
        )

        # Tabulator placeholder
        self.modal_tabulator = pn.Column()

        # Header
        self.modal_header = pn.pane.Markdown("")

        # Button row
        button_row = pn.Row(self.upload_button, self.clear_button)

        # Scrollable content area (header + tabulator)
        self.scrollable_content = pn.Column(
            self.modal_header,
            self.modal_tabulator,
            scroll=True,
            max_height=500,
        )

        # Create modal with all content
        self.modal = pn.layout.Modal(
            self.scrollable_content,
            self.status_pane,
            button_row,
            name="Review Changes",
            show_close_button=True,
            background_close=True,
        )

        # Set up button callbacks
        self.upload_button.on_click(self._on_upload)
        self.clear_button.on_click(self._on_clear)

    def _on_upload(self, event):
        """Handle submit button click in modal"""
        self.upload_button.loading = True
        success, message = self.data.submit_changes_to_docdb(self.final_record)
        self.upload_button.loading = False

        if success:
            self.status_pane.object = f"✅ **{message}**"
            self.upload_button.disabled = True
            self.refresh_page()
        else:
            self.status_pane.object = f"❌ **Error:** {message}"
            self.upload_button.button_type = "danger"

    def _on_clear(self, event):
        """Handle clear button click in modal"""
        self.clear_button.loading = True
        self.data.clear_changes_cache()
        self.clear_button.loading = False
        self.status_pane.object = "✅ **All changes cleared**"
        self.refresh_page()

    def _update_modal_content(self):
        """Update the modal content with current preview data"""
        # Reset status and buttons
        self.status_pane.object = ""
        self.upload_button.disabled = True
        self.upload_button.button_type = "danger"

        preview_df, self.final_record = self.data.get_submission_data()

        if preview_df.empty:
            self.modal_header.object = "## No changes to preview"
            self.modal_tabulator.clear()
            return

        change_count = len(preview_df[preview_df["has_changes"]])

        if change_count > 0:
            self.upload_button.disabled = False
            self.upload_button.button_type = "success"

        # Update header
        self.modal_header.object = (
            f"**{change_count} metrics** with pending changes. Changed rows are highlighted in yellow."
        )

        # Create Tabulator with styling
        tabulator = pn.widgets.Tabulator(
            preview_df,
            disabled=True,
            show_index=False,
            height=400,
            min_width=1000,
            hidden_columns=["has_changes"],
            titles={
                "metric_name": "Metric Name",
                "current_value": "Current Value",
                "current_status": "Current Status",
                "new_value": "New Value",
                "new_status": "New Status",
            },
            widths={
                "current_value": 150,
                "current_status": 150,
                "new_value": 150,
                "new_status": 150,
            },
            stylesheets=[
                """
                .tabulator-row {
                    font-size: 12px;
                }
                .tabulator-cell {
                    padding: 4px 8px;
                }
                """
            ],
        )

        # Apply row styling based on has_changes
        for idx, row in preview_df.iterrows():
            if row["has_changes"]:
                tabulator.style.apply(
                    lambda x: ["background-color: #fff3cd; font-weight: normal;"] * len(x), subset=pd.IndexSlice[idx, :]
                )
            else:
                tabulator.style.apply(
                    lambda x: ["background-color: #f8f9fa; color: #6c757d;"] * len(x), subset=pd.IndexSlice[idx, :]
                )

        # Update tabulator
        self.modal_tabulator.clear()
        self.modal_tabulator.append(tabulator)

    def _get_change_info(self, dirty: pd.DataFrame):
        """Wrap the change count in a static text widget"""
        self._change_info.value = f"Pending changes: {len(dirty)}"
        return self._change_info

    def _redirect_to_login(self):
        """Redirect users to the login page"""
        print("Redirecting to login page...")
        self.hidden_html.object = f"<script>window.location.href = '/login?next={pn.state.location.href}';</script>"

    def _submit_changes(self, *event):
        """Login or submit changes to the QC data"""

        # Re-direct users to login if they aren't already
        if pn.state.user == "guest":
            self._redirect_to_login()
            return

        # Update modal content and show it
        self._update_modal_content()
        self.modal.show()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False

        self.submit_button = pn.widgets.Button(
            name="Review changes" if pn.state.user != "guest" else "Log in",
            button_type="success",
            on_click=self._submit_changes,
        )
        self._change_info = pn.widgets.StaticText(value="")
        self.change_info = pn.bind(self._get_change_info, self.data.param.changes)

    def __panel__(self):
        """Create and return the SubmitPanel layout"""

        return pn.Column(
            self.modal,
            self.submit_button,
            self.change_info,
            self.hidden_html,
            styles=OUTER_STYLE,
            sizing_mode="stretch_height",
        )
