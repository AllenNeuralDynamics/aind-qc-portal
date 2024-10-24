import panel as pn
from aind_data_schema.core.quality_control import Status, QCMetric, QCStatus
from aind_data_schema.base import AwareDatetimeWithDefault
from datetime import datetime
import html

from aind_qc_portal.panel.custom_metrics import CustomMetricValue
from aind_qc_portal.utils import md_style
from urllib.parse import urlparse


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

    @property
    def data(self):
        return self._data

    def set_value(self, event):
        self._set_value(event.new)

    def _set_value(self, value):
        print(f'Updating metric value to: {value}')
        self._data.value = value
        self.parent.set_dirty()

    def set_status(self, event):
        self._set_status(Status(event.new))

    def _set_status(self, status):
        if not isinstance(status, Status):
            status = Status(status)
        print(f'Updating metric status to: {status.value}')

        self._data.status_history.append(QCStatus(
            evaluator="[TODO]",
            status=status,
            timestamp=datetime.now(),
        ))

        self.parent.set_dirty()

    def panel(self):
        """Build a Panel object representing this metric object

        Returns
        -------
        _type_
            _description_
        """
        if self._data.reference:
            if "http" in self._data.reference:
                parsed_url = urlparse(self._data.reference)

                if parsed_url.path.endswith(".png") or parsed_url.path.endswith(".jpg"):
                    self.reference_img = pn.pane.Image(self._data.reference, sizing_mode='scale_width', max_width=1200)
                elif "neuroglancer" in self._data.reference:
                    iframe_html = f'<iframe src="{self._data.reference}" style="height:100%; width:100%" frameborder="0"></iframe>'
                    self.reference_img = pn.pane.HTML(iframe_html, sizing_mode='stretch_both')
                else:
                    self.reference_img = pn.widgets.StaticText(value=f'Reference: <a target="_blank" href="{self._data.reference}">link</a>')
            elif "s3" in self._data.reference:
                self.reference_img = pn.widgets.StaticText(value=f"s3 reference: {self._data.reference}")

            elif self._data.reference == "ecephys-drift-map":
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
            name=self._data.name,
        )
        return row

    def metric_panel(self):
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
        elif isinstance(value, dict):
            try:
                custom_value = CustomMetricValue(value, self._set_value, self._set_status)
                auto_value = True
                auto_state = custom_value.auto_state
                value_widget = custom_value.panel
            except ValueError as e:
                print(e)
                value_widget = pn.widgets.JSONEditor(name=name)
        else:
            value_widget = pn.pane(f"Can't deal with type {type(value)}")

        if not auto_value:
            value_widget.value = value
            value_widget.param.watch(self.set_value, 'value')

        state_selector = pn.widgets.Select(value=self._data.status.status.value, options=["Pass", "Fail", "Pending"], name="Metric status")
        if auto_state:
            state_selector.disabled = True
        else:
            state_selector.param.watch(self.set_status, 'value')

        header = pn.pane.Markdown(md)

        col = pn.Column(header, pn.WidgetBox(value_widget, state_selector), width=350)

        return col
