"""Notes panel"""

import panel as pn
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.view_contents.data import ViewData


class NotesPanel(PyComponent):
    """Panel for displaying and editing QC notes"""

    def __init__(self, data: ViewData):
        super().__init__()
        self._data = data
        self._init_panel_objects()

    def _init_panel_objects(self):
        is_guest = not hasattr(pn.state, "user") or pn.state.user == "guest"
        self.notes_input = pn.widgets.TextAreaInput(
            name="Notes",
            value=self._data.current_notes,
            disabled=is_guest,
            placeholder="Add notes..." if not is_guest else "Log in to edit notes",
            sizing_mode="stretch_width",
            height=90,
        )
        if not is_guest:
            self.notes_input.param.watch(self._on_notes_change, "value")

    def _on_notes_change(self, event):
        self._data.submit_notes_change(event.new)

    def __panel__(self):
        return pn.Column(
            self.notes_input,
            styles=OUTER_STYLE,
            sizing_mode="stretch_width",
        )
