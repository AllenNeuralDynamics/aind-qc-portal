import panel as pn
import param
from panel.custom import PyComponent


class Settings(PyComponent):
    """Settings for the QC view application"""

    group_by = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        super().__init__()

        self.group_by = default_grouping
        self.grouping_options = grouping_options

        pn.state.location.sync(self, {"group_by": "group_by"})

    def _clear_grouping(self, *event):
        """Clear the grouping selection"""
        self.group_by = []

    def __panel__(self):
        """Create and return the settings panel"""
        multichoice = pn.widgets.MultiChoice.from_param(
            self.param.group_by,
            name="Group metrics by these tags/modalities:",
            options=self.grouping_options,
            sizing_mode="stretch_width",
        )
        clear = pn.widgets.Button(
            name="Clear",
            button_type="danger",
            width=80,
            on_click=self._clear_grouping,
        )

        return pn.Row(multichoice, clear)
