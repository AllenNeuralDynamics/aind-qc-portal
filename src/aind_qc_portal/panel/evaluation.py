import panel as pn
from aind_data_schema.core.quality_control import QCEvaluation

from aind_qc_portal.panel.metric import QCMetricPanel
from aind_qc_portal.utils import md_style, status_html


class QCEvalPanel:

    def __init__(self, parent, qc_evaluation: QCEvaluation):
        """Build an Evaluation object, should only be called by QualityControl()

        Parameters
        ----------
        evaluation_data : dict
            See aind_data_schema.core.quality_control Evaluation
        """
        self.parent = parent
        self.update(qc_evaluation)

    def update(self, evaluation_data: QCEvaluation):
        self._data = evaluation_data

        self.metrics = []
        for qc_metric in self._data.metrics:
            self.metrics.append(QCMetricPanel(self.parent, qc_metric))

    @property
    def data(self):
        # allow the metrics to update themselves before returning
        self._data.metrics = [metric.data for metric in self.metrics]

        return self._data

    def set_notes(self, event):
        self._data.notes = event.new
        self.parent.set_dirty()

    def panel(self):
        """Build a Panel object representing this Evaluation"""
        objects = []
        for metric in self.metrics:
            objects.append(metric.panel())

        allow_failing_str = (
            "Metrics are allowed to fail."
            if self._data.allow_failed_metrics
            else ""
        )

        md = f"""
{md_style(12, self._data.description if self._data.description else "*no description provided*")}
{md_style(8, f"Current state: **{status_html(self._data.status())}**")}
{md_style(8, f"Contains **{len(self._data.metrics)}** metrics. {allow_failing_str}")}
"""

        header = pn.pane.Markdown(md)

        notes = pn.widgets.TextAreaInput(
            name="Notes:",
            value=self._data.notes,
            placeholder="no notes provided",
        )

        if pn.state.user == "guest":
            notes.disabled = True
        else:
            notes.param.watch(self.set_notes, "value")

        header_row = pn.Row(header, notes, max_height=1200)

        accordion = pn.Accordion(*objects, sizing_mode="stretch_width", max_height=1200)
        accordion.active = [0]

        col = pn.Column(header_row, accordion, name=self._data.name)

        return col
