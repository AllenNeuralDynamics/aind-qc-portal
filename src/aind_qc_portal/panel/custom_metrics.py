""" Custom metric value class for handling custom metric values in the QC Portal UI"""

from datetime import datetime, timezone
import panel as pn
import json
from typing import Any

from aind_qcportal_schema.metric_value import (
    CheckboxMetric,
    DropdownMetric,
    RulebasedMetric,
    CurationMetric,
    CurationHistory,
)
from aind_data_schema.core.quality_control import Status
from aind_qc_portal.utils import get_user_name


def attempt_custom_repairs(data: dict) -> dict:
    """Attempt to repair a custom metric value that has been corrupted

    [todo: this should be removed]

    Parameters
    ----------
    data : dict

    Returns
    -------
    dict
    """
    # Usually this is caused by a value field that doesn't match the allowed defaults
    if data["type"] == "dropdown":
        if "value" not in data or data["value"] not in data["options"]:
            data["value"] = ""
    elif data["type"] == "checkbox":
        if "value" not in data or not isinstance(data["value"], list):
            data["value"] = []

    return data


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
        self.type = None

        if "type" in data:
            if data["type"] == "dropdown":
                try:
                    self._data = DropdownMetric.model_validate(data)
                except Exception:
                    self._data = DropdownMetric.model_validate(attempt_custom_repairs(data))
                self._auto_state = self._data.status is not None
                self._dropdown_helper(data)
            elif data["type"] == "checkbox":
                try:
                    self._data = CheckboxMetric.model_validate(data)
                except Exception:
                    self._data = CheckboxMetric.model_validate(attempt_custom_repairs(data))
                self._auto_state = self._data.status is not None
                self._checkbox_helper(data)
            elif data["type"] == "curation" or data["type"] == "ephys_curation":
                data["type"] = "curation"  # todo: remove when EphysCurationMetric removed
                self._data = CurationMetric.model_validate(data)
                self._auto_state = False
                self._curation_helper(data)
            else:
                raise ValueError("Unknown type for custom metric value")
        elif "rule" in data:
            self._data = RulebasedMetric.model_validate_json(json.dumps(data))
            self._auto_state = True
            self._rulebased_helper(data)
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
                    CurationMetric,
                    RulebasedMetric,
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
        elif isinstance(self._data, CurationMetric):
            print(f"Updating curation value to {value}")
            self._data.curations.append(json.dumps(value))
            self._data.curation_history.append(
                CurationHistory(
                    curator=get_user_name(),
                    timestamp=datetime.now(timezone.utc),
                )
            )
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
        # Update the value according to the t ype of custom metric
        self.update_value(event.new)

        # Push the new value into the upstream QCMetric.value field
        self._value_callback(self._data)

        # Handle state updates
        if self._auto_state:
            try:
                if not self._data.value:
                    self._status_callback(Status.PENDING)
                else:
                    if isinstance(self._data.value, list):
                        values = [self._data.status[self._data.options.index(value)] for value in self._data.value]
                        if any(values == Status.FAIL for value in values):
                            self._status_callback(Status.FAIL)
                        elif any(values == Status.PENDING for value in values):
                            self._status_callback(Status.PENDING)
                        else:
                            self._status_callback(Status.PASS)
                    else:
                        idx = self._data.options.index(self._data.value)
                        self._status_callback(self._data.status[idx])
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

    def _curation_helper(self, data: dict):
        """Helper function for curation metric values"""
        self._panel = pn.widgets.JSONEditor(
            name="Value",
            value=data["curations"] if "curations" in data else {},
            sizing_mode="stretch_width",
            disabled=True,
        )

    def _rulebased_helper(self, data: dict):
        """Helper function for rulebased metric values"""
        self._panel = pn.widgets.StaticText(value="Todo")
