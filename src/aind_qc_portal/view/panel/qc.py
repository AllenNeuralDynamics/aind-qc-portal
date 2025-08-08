from panel.custom import PyComponent
import panel as pn
import param
import pandas as pd


class Metric(PyComponent):
    """Panel for displaying a single metric"""
    
    name = param.String(default="")
    description = param.String(default="")
    value = param.String(default="")
    reference = param.String(default="")

    def __init__(self, name: str, value: str, reference: str):
        super().__init__()
        self.name = name
        self.value = value
        self.reference = reference

    def __panel__(self):
        """Create and return the Panel layout"""

        # Name and description

        # Value/Status column
        return pn.Column(
            pn.pane.Markdown(f"**{self.name}**"),
            pn.pane.Str(self.value),
            pn.pane.Str(self.reference),
            styles={"margin": "10px", "padding": "10px", "border": "1px solid #ccc"},
        )


class MetricValue(PyComponent):
    """Panel for displaying a single metric value"""

    name = param.String(default="")
    value = param.String(default="")

    def __init__(self, name: str, value: str):
        super().__init__()
        self.name = name
        self.value = value

    def __panel__(self):
        """Create and return the Panel layout"""

        return pn.Column(
            pn.pane.Markdown(f"**{self.name}**"),
            pn.pane.Str(self.value),
            styles={"margin": "10px", "padding": "10px", "border": "1px solid #ccc"},
        )


class MultiMetric(PyComponent):
    """Panel for displaying multiple metrics that share a reference"""

    names = param.List(default=[])
    values = param.List(default=[])
    reference = param.String(default="")

    def __init__(self, names: list, values: list, reference: str):
        super().__init__()
        self.names = names
        self.values = values
        self.reference = reference

    def __panel__(self):
        """Create and return the Panel layout"""

        # Create a panel for each metric
        metrics = [
            Metric(name=name, value=value, reference=self.reference)
            for name, value in zip(self.names, self.values)
        ]

        return pn.Column(*metrics, styles={"margin": "10px", "padding": "10px", "border": "1px solid #ccc"})


class Metrics(PyComponent):
    """Panel for displaying the groups and individual metrics

    Constructed from a tab view of the groups and an accordion for the metrics.
    """

    data = param.DataFrame(default=None, allow_None=True)

    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self.data = data
        self._init_panel_objects()

    def update_data(self, new_data: pd.DataFrame):
        """Update the data in the panel"""
        self.data = new_data

    def __panel__(self):
        """Create and return the Panel layout"""

        # Build the metric accordions

        # Build the group tabs

        return pn.Column(
            sizing_mode="stretch_width",
        )


class MetricGroups(PyComponent):
    """Panel for displaying the metric groups and their status"""

    groups = param.List(default=[])
    grouping_options = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        super().__init__()

        self.groups = default_grouping
        self.grouping_options = grouping_options

    def __panel__(self):
        """Create and return the settings panel"""
        return pn.Column(
            pn.widgets.MultiChoice(
                name="Group metrics by these tags/modalities:",
                options=self.grouping_options,
                value=self.groups,
            ),
            styles=OUTER_STYLE,
            width=400,
        )


class 