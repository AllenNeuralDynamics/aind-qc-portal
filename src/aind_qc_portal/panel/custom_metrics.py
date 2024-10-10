import panel as pn
from aind_qcportal_schema.metric_value import (
    CheckboxMetric,
    DropdownMetric,
    RulebasedMetric,
)


class CustomMetricValue:

    def __init__(self, data: dict, value_callback, status_callback):
        """Build a new CustomMetricValue object from a metric's value

        Parameters
        ----------
        data : dict
            Dictionary containing data dumped from one of the metric_value classes 
        """

        self._panel = None
        self._data = data
        self._value_callback = value_callback
        self._status_callback = status_callback

        if "type" in data:
            if data["type"] == "dropdown":
                self._dropdown_helper(data)
            elif data["type"] == "checkbox":
                self._dropdown_helper(data)
            else:
                raise ValueError("Unknown type for custom metric value")
        elif "rule" in data:
            self._rulebased_helper(data)
        else:
            raise ValueError("Unknown type for custom metric value")

    @property
    def panel(self):
        """Panel pane for this custom metric value
        """
        return self._panel

    @property
    def auto_state(self) -> bool:
        """Where the custom value's state will get automatically updated
        """
        return "rule" in self._data or self._data.get("status")

    def _callback_helper(self, event):        
        updated_data = self._data
        updated_data["value"] = event.new
        self._value_callback(updated_data)

        if self._data.get("status"):
            self._status_callback(self._data["status"][event.new])

    def _dropdown_helper(self, data: dict):
        self._panel = pn.widgets.Select(
            name='Value',
            options=data["options"]
        )
        self._panel.value = data["options"][0]

        # watch the selector and pass event updates back through the callback
        # self._panel.param.watch(self._callback_helper, "value")

    def _checkbox_helper(self, data: dict):
        self._panel = pn.widgets.MultiChoice(
            name='Value',
            options=data["options"]
        )

        # watch the selector and pass event updates back through the callback
        self._panel.param.watch(self._callback_helper, "value")

    def _rulebased_helper(self, data: dict):
        self._panel = pn.pane("todo")
