import panel as pn
import json

from aind_qcportal_schema.metric_value import (
    CheckboxMetric,
    DropdownMetric,
    RulebasedMetric,
    CurationMetric,
    CurationHistory
)
from aind_data_schema.core.quality_control import Status


class CustomMetricValue:
    """This class is really ugly because of how it handles multiple types... please refactor me"""

    def __init__(self, data: dict, value_callback, status_callback):
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

        if "type" in data:
            if data["type"] == "dropdown":
                self._data = DropdownMetric.model_validate_json(
                    json.dumps(data)
                )
                self._auto_state = self._data.status is not None
                self._dropdown_helper(data)
            elif data["type"] == "checkbox":
                self._data = CheckboxMetric.model_validate_json(
                    json.dumps(data)
                )
                self._auto_state = self._data.status is not None
                self._checkbox_helper(data)
            elif data["type"] == "curation":
                self._data = 
            else:
                raise ValueError("Unknown type for custom metric value")
        elif "rule" in data:
            self._data = RulebasedMetric.model_validate_json(json.dumps(data))
            self._auto_state = True
            self._rulebased_helper(data)
        else:
            raise ValueError("Unknown custom metric value")

    @property
    def panel(self):
        """Panel pane for this custom metric value"""
        return self._panel

    @property
    def auto_state(self) -> bool:
        """Where the custom value's state will get automatically updated"""
        return self._auto_state

    def _callback_helper(self, event):
        updated_data = self._data
        if hasattr(updated_data, "value"):
            updated_data.value = event.new
        else:
            updated_data["value"] = event.new

        if isinstance(updated_data, dict):
            self._value_callback(json.dumps(updated_data))
        else:
            self._value_callback(updated_data.model_dump())

        if self._auto_state:
            try:
                if not updated_data.value:
                    self._status_callback(Status.PENDING)
                else:
                    if isinstance(updated_data.value, list):
                        values = [
                            updated_data.status[
                                updated_data.options.index(value)
                            ]
                            for value in updated_data.value
                        ]
                        if any(values == Status.FAIL for value in values):
                            self._status_callback(Status.FAIL)
                        elif any(values == Status.PENDING for value in values):
                            self._status_callback(Status.PENDING)
                        else:
                            self._status_callback(Status.PASS)
                    else:
                        idx = updated_data.options.index(updated_data.value)
                        self._status_callback(updated_data.status[idx])
            except Exception as e:
                print(e)
                self._status_callback(Status.PENDING)

        self._data = updated_data

    def _dropdown_helper(self, data: dict):
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

    def _rulebased_helper(self, data: dict):
        self._panel = pn.widgets.StaticText(value="Todo")
