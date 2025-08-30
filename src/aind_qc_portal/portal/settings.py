

import panel as pn
from panel.custom import PyComponent
import param


class Settings(PyComponent):

    show_full_metadata_path = param.Boolean(default=True)

    def __init__(self):
        """Initialize the Settings app"""
        super().__init__()
        self._init_panel_components()

    def _init_panel_components(self):
        """Initialize the components of the Settings app"""
        
        toggle = pn.widgets.Checkbox.from_param(
            self.param.show_full_metadata_path,
            name="Show Full Metadata Path",
        )
        
        header = pn.pane.Markdown("### Settings")

        self.panel = pn.Modal(
            header,
            toggle,
        )

    def __panel__(self):
        """Return the Panel representation of the Settings app"""

        return self.panel


settings = Settings()
