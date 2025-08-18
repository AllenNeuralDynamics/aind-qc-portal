"""Login and submit panels"""

from panel.custom import PyComponent
import panel as pn

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.layout import OUTER_STYLE


class SubmitPanel(PyComponent):
    """Panel for submitting QC data"""

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
        response = qc_update_to_id(self.id, self.data)

        # Deal with errors, on success refresh page to pull new data
        if response.status_code != 200:
            self.submit_error.value = f"Error ({response.status_code}) submitting changes: {response.text}"
            self.submit_button.button_type = "danger"
            return
        else:
            self.submit_button.disabled = True
            self.changes = 0
            self.change_info.value = f"{self.changes} pending changes"
            self._refresh()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False

        self.submit_button = pn.widgets.Button(
            name="Submit changes" if pn.state.user != "guest" else "Log in",
            button_type="success",
            on_click=self._submit_changes,
        )
        self._change_info = pn.widgets.StaticText(value="")
        self.change_info = pn.bind(self._get_change_info, self.data.param.dirty)

    def __panel__(self):
        """Create and return the SubmitPanel layout"""

        return pn.Column(
            self.submit_button,
            self.change_info,
            self.hidden_html,
            # self.submit_info,
            # self.submit_error,
            styles=OUTER_STYLE,
        )
