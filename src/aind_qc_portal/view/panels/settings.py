from panel.custom import PyComponent
import param
import panel as pn


class Settings(PyComponent):
    """Settings for the QC view application"""

    group_by = param.List(default=[])
    grouping_options = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        super().__init__()

        self.group_by = default_grouping
        self.grouping_options = grouping_options

    def __panel__(self):
        """Create and return the settings panel"""
        multichoice = pn.widgets.MultiChoice(
            name="Group metrics by these tags/modalities:",
            options=self.grouping_options,
            value=self.group_by,
        )

        # Bind the widget value to the parameter
        multichoice.link(self, value='group_by')

        return pn.Column(multichoice)