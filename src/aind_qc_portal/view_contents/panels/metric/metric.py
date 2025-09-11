from typing import Any, Callable

import panel as pn
from aind_data_schema.core.quality_control import Status
from aind_qcportal_schema.metric_value import CheckboxMetric, DropdownMetric


class CustomMetricValue:
    """This class is really ugly because of how it handles multiple types... please refactor me"""

    def __init__(self, data: dict, value_callback: Callable, status_callback: Callable):
        """Build a new CustomMetricValue object from a metric's value

        Parameters
        ----------
        data : dict
            Dictionary containing data dumped from one of the metric_value classes
        """

        self._panel = None
        self._auto_state = False
        self._value_callback = value_callback
        self._status_callback = status_callback
        self.type = None

        if "type" in data:
            if data["type"] == "dropdown":
                try:
                    self._data = DropdownMetric.model_validate(data)
                    self._auto_state = self._data.status is not None
                    self._dropdown_helper(data)
                except Exception as e:
                    print(f"Failed to validate dropdown metric: {data}")
                    raise
            elif data["type"] == "checkbox":
                self._data = CheckboxMetric.model_validate(data)
                self._auto_state = self._data.status is not None
                self._checkbox_helper(data)
            else:
                raise ValueError(f"Unknown type '{data["type"]}' for custom metric value")
        else:
            raise ValueError("Unknown custom metric value")

    @classmethod
    def is_custom_metric(cls, data: Any) -> bool:
        """Check if the data is a custom metric value

        Parameters
        ----------
        data : Any

        Returns
        -------
        bool
        """
        if isinstance(data, dict):
            return "type" in data or "rule" in data
        else:
            return isinstance(
                data,
                (
                    DropdownMetric,
                    CheckboxMetric,
                ),
            )

    def update_value(self, value):
        """
        Update to a new value and return what should be stored in the QCMetric.value field
        """
        if isinstance(self._data, DropdownMetric):
            print(f"Updating dropdown value to {value}")
            self._data.value = value
        elif isinstance(self._data, CheckboxMetric):
            print(f"Updating checkbox value to {value}")
            self._data.value = value
        else:
            print(f"Updating dictionary value to {value}")
            self._data.value = value

        return self._data

    def panel(self):
        """Panel pane for this custom metric value"""
        return self._panel

    @property
    def data(self):
        """Return the data object"""
        return self._data

    @property
    def auto_state(self) -> bool:
        """Where the custom value's state will get automatically updated"""
        return self._auto_state

    def _callback_helper(self, event):
        """Helper function for custom metric value callbacks, called by Panel event callback
        when the user changes the value of the metric
        """
        # Update the metric's value
        new_value = self.update_value(event.new)

        # Update the metric value stored in the metric object
        self._value_callback(new_value)

        # Update the status if it is supposed to be updated automatically
        if self._auto_state:
            try:
                if isinstance(self._data, CheckboxMetric):
                    if self._data.status:
                        # Map each selected value to its status, then reduce using the QC metric pattern
                        values = [self._data.status[self._data.options.index(value)] for value in self._data.value]
                        if Status.FAIL in values:
                            self._status_callback(Status.FAIL)
                        elif Status.PENDING in values:
                            self._status_callback(Status.PENDING)
                        else:
                            self._status_callback(Status.PASS)
                    elif isinstance(self._data, DropdownMetric):
                        if self._data.status:
                            idx = self._data.options.index(self._data.value)
                            self._status_callback(self._data.status[idx])
                        else:
                            print(f"Unsupported metric type for auto state update: {self._data}")
                            self._status_callback(Status.PENDING)
            except Exception as e:
                print(e)
                self._status_callback(Status.PENDING)

    def _dropdown_helper(self, data: dict):
        """Helper function for dropdown metric values"""
        self._panel = pn.widgets.Select(
            name="Value",
            options=[""] + data["options"],
        )
        if data["value"]:
            self._panel.value = data["value"]
        else:
            self._panel.value = ""

        # watch the selector and pass event updates back through the callback
        self._panel.param.watch(self._callback_helper, "value")

    def _checkbox_helper(self, data: dict):
        """Helper function for checkbox metric values"""
        self._panel = pn.widgets.MultiChoice(
            name="Value",
            options=data["options"],
        )
        if (
            data["value"]
            and isinstance(data["value"], list)
            and all(value in data["options"] for value in data["value"])
        ):
            self._panel.value = [data["value"]]
        else:
            print("Checkbox value not in options")
            self._panel.value = []

        # watch the selector and pass event updates back through the callback
        self._panel.param.watch(self._callback_helper, "value")
