import panel as pn
from aind_data_schema.core.quality_control import Status, QCMetric, QCStatus
from datetime import datetime
import pandas as pd

from aind_qc_portal.panel.custom_metrics import CustomMetricValue
from aind_qc_portal.panel.media import Media
from aind_qc_portal.utils import md_style


class QCMetricPanel:

    def __init__(self, parent, qc_metric: QCMetric):
        """Build a Metric object, should only be called by Evaluation()

        Parameters
        ----------
        evaluation_data : dict
            See aind_data_schema.core.quality_control Evaluation
        """
        self._data = qc_metric
        self.parent = parent
        self.reference_img = None
        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False

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

        self._data.status_history.append(
            QCStatus(
                evaluator=f"{pn.state.user_info['given_name']} {pn.state.user_info['family_name']}",
                status=status,
                timestamp=datetime.now(),
            )
        )

        self.parent.set_dirty()

    def panel(self):
        """Build the full panel for this metric with both the metric status and reference media"""

        if self._data.reference:
            self.reference_img = Media(
                self._data.reference, self.parent
            ).panel()
        else:
            self.reference_img = "No references included"

        row = pn.Row(
            self.metric_panel(),
            self.reference_img,
            name=self._data.name,
            sizing_mode="stretch_both",
        )
        return row

    def metric_panel(self):
        """Build the left column with the metric status and value, plus any custom controls"""

        # Markdown header to display current state
        md = f"""
{md_style(10, f"Current state: {self._data.status.status.value}")}
{md_style(8, self._data.description if self._data.description else "*no description provided*")}
{md_style(8, f"Value: {self._data.value}")}
"""
        name = self._data.name
        value = self._data.value

        auto_value = False
        auto_state = False
        if isinstance(value, bool):
            value_widget = pn.widgets.Checkbox(name=name)
        elif isinstance(value, str):
            value_widget = pn.widgets.TextInput(name=name)
        elif isinstance(value, float):
            value_widget = pn.widgets.FloatInput(name=name)
        elif isinstance(value, int):
            value_widget = pn.widgets.IntInput(name=name)
        elif isinstance(value, list):
            df = pd.DataFrame({"values": value})
            value_widget = pn.pane.DataFrame(df)
            auto_value = True
        elif isinstance(value, dict):
            # first, check if every key/value pair has the same length, if so coerce to a dataframe
            if all([isinstance(v, list) for v in value.values()]) and all(
                [
                    len(v) == len(value[list(value.keys())[0]])
                    for v in value.values()
                ]
            ):
                df = pd.DataFrame(value)
                value_widget = pn.pane.DataFrame(df)
            else:
                try:
                    custom_value = CustomMetricValue(
                        value, self._set_value, self._set_status
                    )
                    auto_value = True
                    auto_state = custom_value.auto_state
                    value_widget = custom_value.panel
                except ValueError as e:
                    print(e)
                    value_widget = pn.widgets.JSONEditor(name=name)
        else:
            value_widget = pn.pane(f"Can't deal with type {type(value)}")

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
        )

        return col
