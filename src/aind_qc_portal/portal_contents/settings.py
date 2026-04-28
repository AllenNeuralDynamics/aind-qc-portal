"""Settings"""

import panel as pn
import param
from panel.custom import PyComponent


class Settings(PyComponent):
    """Settings for the Portal app"""

    show_full_metadata_path = param.Boolean(default=True)
    show_query_editor = param.Boolean(default=False)

    def __init__(self):
        """Initialize the Settings app"""
        super().__init__()
        self._init_panel_components()

    def _init_panel_components(self):
        """Initialize the components of the Settings app"""
        metadata_toggle = pn.widgets.Checkbox.from_param(
            self.param.show_full_metadata_path,
            name="Show Full Metadata Path",
        )

        query_toggle = pn.widgets.Checkbox.from_param(
            self.param.show_query_editor,
            name="Show Query Editor",
        )

        header = pn.pane.Markdown("### Settings")

        self.panel = pn.Modal(
            header,
            metadata_toggle,
            query_toggle,
        )

    def __panel__(self):
        """Return the Panel representation of the Settings app"""

        return self.panel


settings = Settings()
