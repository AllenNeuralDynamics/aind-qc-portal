"""Login and submit panels with Material UI support"""

import panel as pn
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.view_contents.data import ViewData
from aind_qc_portal.material_ui import (
    create_button,
    create_alert,
    create_card,
)


class SubmitPanel(PyComponent):
    """Panel for submitting QC data with Material UI"""

    def __init__(self, data: ViewData):
        super().__init__()
        self.data = data
        self._init_panel_objects()

    def _get_change_info(self, dirty: int):
        """Wrap the change count in a static text widget"""
        self._change_info.value = f"Pending changes: {dirty}"
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

        # Push the changes to DocDB
        from aind_qc_portal.view_contents.data import qc_update_to_id
        response = qc_update_to_id(self.id, self.data)

        # Deal with errors, on success refresh page to pull new data
        if response.status_code != 200:
            # Show error alert
            self.submit_alert = create_alert(
                f"Error ({response.status_code}) submitting changes: {response.text}",
                severity='error'
            )
            self.submit_button.button_type = "danger"
            return
        else:
            # Show success alert
            self.submit_alert = create_alert(
                "✅ Changes saved successfully!",
                severity='success'
            )
            self.submit_button.disabled = True
            self.changes = 0
            self.change_info.value = f"{self.changes} pending changes"
            # Refresh after short delay to show success message
            pn.state.execute_callback(self._refresh, delay=2000)

    def _refresh(self):
        """Refresh the page to pull new data"""
        # Reload the current page
        pn.state.location.reload = True

    def _init_panel_objects(self):
        """Initialize panel objects with Material UI"""

        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False

        # Use Material UI button
        button_name = "Submit changes" if pn.state.user != "guest" else "Log in"
        button_type = "success" if pn.state.user != "guest" else "primary"
        
        self.submit_button = create_button(
            name=button_name,
            button_type=button_type,
        )
        self.submit_button.on_click = self._submit_changes
        
        self._change_info = pn.widgets.StaticText(value="")
        self.change_info = pn.bind(self._get_change_info, self.data.param.dirty)
        
        # Alert placeholder
        self.submit_alert = None

    def __panel__(self):
        """Create and return the SubmitPanel layout"""
        
        components = [
            self.submit_button,
            self.change_info,
            self.hidden_html,
        ]
        
        # Add alert if present
        if self.submit_alert:
            components.insert(0, self.submit_alert)

        # Wrap in Material Card
        return create_card(
            title="Submit Changes",
            children=components,
            styles=OUTER_STYLE,
        )
    