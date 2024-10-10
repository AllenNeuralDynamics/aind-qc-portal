import panel as pn
from aind_qcportal_schema.metric_value import DropdownMetric, CheckboxMetric, RulebasedMetric


class CustomMetricValue:

    def __init__(self, data: dict, value_callback, status_callback):
        """Build a new CustomMetricValue object from a metric's value

        Parameters
        ----------
        data : dict
            Dictionary containing data dumped from one of the metric_value classes 
        """
        print(type(data))
        print(data)

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
        return self._panel

    def _callback_helper(self, event):
        print("here")
        print(event.new)
        self._value_callback = event.new
        if "status" in self._data:
            self._status_callback(self._data["status"][event.new])

    def _dropdown_helper(self, data: dict):
        self._panel = pn.widgets.Select(
            name='Value',
            options=data["options"]
        )
        print(data["options"])
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
