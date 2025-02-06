import panel as pn
from aind_data_schema.core.quality_control import Status, QCMetric, QCStatus
from datetime import datetime
import pandas as pd
from typing import List, Union

from aind_qc_portal.panel.custom_metrics import CustomMetricValue
from aind_qcportal_schema.metric_value import CurationHistory
from aind_qc_portal.panel.media import Media
from aind_qc_portal.utils import replace_markdown_with_html


class QCMetricMediaPanel:
    """Object to generate just the media panel for a metric"""

    def __init__(self, qc_metric: QCMetric, parent):
        """Create a QCMetricMediaPanel object"""
        self.reference = qc_metric.reference
        self.parent = parent
        self.value_callback = None

    def register_callback(self, value_callback):
        self.value_callback = value_callback

    def panel(self):
        """Build the media reference"""

        if self.reference:
            self.reference_media = Media(
                self.reference,
                self.parent,
                self.value_callback
            ).panel()
        else:
            self.reference_media = "No references included"

        return self.reference_media


class QCMetricValuePanel:
    """Object to generate just the value panel for a metric"""

    def __init__(self, qc_metric: QCMetric, parent):
        """Create a QCMetricValuePanel object"""
        self._data = qc_metric
        self.parent = parent
        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False
        self.type = None

        self.parse_type()

    @property
    def data(self):
        return self._data

    def set_value(self, event):
        """Set value (event callback)"""
        self._set_value(event.new)

    def _set_value(self, value):
        """Set the value of this metric

        Note that this doesn't automatically set_dirty in the parent
        This is because the status_history needs to be updated before a new value can be saved
        """
        print(f"Updating metric value to: {value}")
        if self.type == "custom":
            self._data.value = self.value.update_value(value)
        else:
            self._data.value = value

    def set_status(self, event):
        """Set the status from a Panel event

        Parameters
        ----------
        event : Event
        """
        self._set_status(Status(event.new))

    def _set_status(self, status: Status | str):
        """Set the status of this metric and record

        Parameters
        ----------
        status : Status or str
        """
        if not isinstance(status, Status):
            status = Status(status)
        print(f"Updating metric status to: {status.value}")

        if self.state_selector:
            self.state_selector.value = status.value

        given_name = pn.state.user_info.get("given_name", "")
        family_name = pn.state.user_info.get("family_name", "")

        self._data.status_history.append(
            QCStatus(
                evaluator=f"{given_name} {family_name}",
                status=status,
                timestamp=datetime.now(),
            )
        )

        self.parent.set_submit_dirty()
    
    def parse_type(self):
        """Parse the type of the metric's value field"""

        self.value = self._data.value

        if isinstance(self.value, bool):
            self.type = "checkbox"
        elif isinstance(self.value, str):
            self.type = "text"
        elif isinstance(self.value, float):
            self.type = "float"
        elif isinstance(self.value, int):
            self.type = "int"
        elif isinstance(self.value, list):
            self.type = "list"
        elif isinstance(self.value, dict):
            # first, check if every key/value pair has the same length, if so coerce to a dataframe
            if all([isinstance(v, list) for v in self.value.values()]) and all(
                [
                    len(v) == len(self.value[list(self.value.keys())[0]])
                    for v in self.value.values()
                ]
            ):
                self.type = "dataframe"
            # Check if all values are strings, ints, or floats, we can also coerce to a dataframe for this
            elif all(
                [
                    isinstance(v, str)
                    or isinstance(v, int)
                    or isinstance(v, float)
                    for v in self.value.values()
                ]
            ):
                self.type = "dataframe"
            else:
                # Check if this is a custom metric value, and if not give up and just display the JSON
                try:
                    self.value = CustomMetricValue(
                        self.value, self._set_value, self._set_status
                    )
                    self.type = "custom"
                except ValueError as e:
                    print(e)
                    self.type = "json"
        else:
            self.type = "unknown"


    def value_to_panel(self, name, value):
        """Convert a metric value to a panel object"""

        auto_value = False
        auto_state = False

        if self.type == "checkbox":
            value_widget = pn.widgets.Checkbox(name=name)
            value_widget.value = value
        elif self.type == "text":
            value_widget = pn.widgets.TextInput(name=name)
            value_widget.value = value
        elif self.type == "float":
            value_widget = pn.widgets.FloatInput(name=name)
            value_widget.value = value
        elif self.type == "int":
            value_widget = pn.widgets.IntInput(name=name)
            value_widget.value = value
        elif self.type == "list":
            df = pd.DataFrame({"values": value})
            value_widget = pn.pane.DataFrame(df)
            auto_value = True
        elif self.type == "dataframe":
            auto_value = True
            df = pd.DataFrame(value)
            value_widget = pn.pane.DataFrame(df)
        elif self.type == "custom":
            # Check if this is a custom metric value, and if not give up and just display the JSON
            auto_value = True
            auto_state = self.value.auto_state
            value_widget = self.value.panel()
        elif self.type == "json":
            value_widget = pn.widgets.JSONEditor(name=name)
            value_widget.value = value
        else:
            value_widget = pn.widgets.StaticText(f"Can't deal with type {type(value)}")

        return value_widget, auto_value, auto_state

    def panel(self):
        """Create the metric value panel"""

        # Markdown header to display current state
        md = f"""
{replace_markdown_with_html(10, f"{self._data.name}")}
{replace_markdown_with_html(8, self._data.description if self._data.description else "*no description provided*")}
"""
        name = self._data.name
        value = self._data.value

        # Check if empty, if so set to empty string
        if value is None or value == "" or value == [] or value == {}:
            value = ""

        value_widget, auto_value, auto_state = self.value_to_panel(name, value)

        if pn.state.user == "guest":
            value_widget.disabled = True

        if not auto_value:
            value_widget.value = value
            value_widget.param.watch(self.set_value, "value")

        self.state_selector = pn.widgets.Select(
            value=self._data.status.status.value,
            options=["Pass", "Fail", "Pending"],
            name="Metric status",
        )

        if pn.state.user == "guest":
            self.state_selector.disabled = True
        else:
            if auto_state:
                self.state_selector.disabled = True
            else:
                self.state_selector.param.watch(self.set_status, "value")

        header = pn.pane.Markdown(md)

        col = pn.Column(
            header,
            pn.WidgetBox(value_widget, self.state_selector),
            self.hidden_html,
            width=350,
            max_height=1200,
        )

        return col


class QCMetricPanel:
    """Object which combines one or multiple metric value panels and a reference media panel"""

    def __init__(self, qc_metrics: Union[QCMetricValuePanel, List[QCMetricValuePanel]], qc_media: QCMetricMediaPanel):
        """Build a Metric object, should only be called by Evaluation()

        Parameters
        ----------
        evaluation_data : dict
            See aind_data_schema.core.quality_control Evaluation
        """
        if not isinstance(qc_metrics, List):
            qc_metrics = [qc_metrics]

        self.metrics = qc_metrics
        self.media = qc_media

    def panel(self):
        """Build the full panel for this metric with both the metric status and reference media"""

        if len(self.metrics) == 1:
            name = self.metrics[0]._data.name
        else:
            name = f"Metric group: {self.media.reference}"

        metric_col = pn.Column(*[metric.panel() for metric in self.metrics])

        row = pn.Row(
            metric_col,
            self.media.panel(),
            name=name,
            sizing_mode="stretch_width",
            max_height=1200,
        )
        return row
