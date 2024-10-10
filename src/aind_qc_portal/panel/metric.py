import panel as pn
from aind_data_schema.core.quality_control import Status

from aind_qc_portal.panel.custom_metrics import CustomMetricValue
from aind_qc_portal.utils import md_style


class QCMetricPanel:

    def __init__(self, parent, metric_data: dict):
        """Build a Metric object, should only be called by Evaluation()

        Parameters
        ----------
        evaluation_data : dict
            See aind_data_schema.core.quality_control Evaluation
        """
        self.data = metric_data
        self.parent = parent
        self.reference_img = None
    
    def set_value(self, event):
        self._set_value(event.new)

    def _set_value(self, value):
        self.data.value = value
        self.parent.set_dirty()

    def set_status(self, event):
        self._set_status(Status(event.new))

    def _set_status(self, status):
        if isinstance(status, Status):
            self.data.status.status = status
        else:
            self.data.status.status = Status(status)
        
        self.parent.set_dirty()

    def panel(self):
        """Build a Panel object representing this metric object

        Returns
        -------
        _type_
            _description_
        """
        if self.data.reference:
            if self.data.reference == "ecephys-drift-map":
                self.reference_img = ""
            else:
                self.reference_img = (
                    f"Unable to parse {self.reference_img}"
                )
        else:
            self.reference_img = "No references included"

        row = pn.Row(
            self.metric_panel(),
            self.reference_img,
            name=self.data.name,
        )
        return row

    def metric_panel(self):
        # Markdown header to display current state
        md = f"""
{md_style(10, f"Current state: {self.data.status.status.value}")}
{md_style(8, self.data.description if self.data.description else "*no description provided*")}
{md_style(8, f"Value: {self.data.value}")}
"""
        name = self.data.name
        value = self.data.value

        auto_state = False
        if isinstance(value, bool):
            value_widget = pn.widgets.Checkbox(name=name)
        elif isinstance(value, str):
            value_widget = pn.widgets.TextInput(name=name)
        elif isinstance(value, float):
            value_widget = pn.widgets.FloatInput(name=name)
        elif isinstance(value, int):
            value_widget = pn.widgets.IntInput(name=name)
        elif isinstance(value, dict):
            try:
                custom_value = CustomMetricValue(value, self._set_value, self._set_status)
                auto_state = custom_value.auto_state
                value_widget = custom_value.panel
            except ValueError as e:
                print(e)
                value_widget = pn.widgets.JSONEditor(name=name)
        else:
            value_widget = pn.pane(f"Can't deal with type {type(value)}")

        value_widget.value = value
        value_widget.param.watch(self.set_value, 'value')

        state_selector = pn.widgets.Select(value=self.data.status.status.value, options=["Pass", "Fail", "Pending"], name="Metric status")
        if auto_state:
            state_selector.disabled = True
        else:
            state_selector.param.watch(self.set_status, 'value')

        header = pn.pane.Markdown(md)

        col = pn.Column(header, pn.WidgetBox(value_widget, state_selector))

        return col
