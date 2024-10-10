import panel as pn
from aind_data_schema.core.quality_control import QCEvaluation

from aind_qc_portal.panel.metric import QCMetricPanel
from aind_qc_portal.utils import md_style, status_html


class QCEvalPanel:

    def __init__(self, parent, evaluation_data: dict):
        """Build an Evaluation object, should only be called by QualityControl()

        Parameters
        ----------
        evaluation_data : dict
            See aind_data_schema.core.quality_control Evaluation
        """
        self.parent = parent
        self.update(evaluation_data)

    def update(self, evaluation_data: QCEvaluation):
        self.data = evaluation_data

        self.metrics = []
        for qc_metric in self.data.metrics:
            self.metrics.append(QCMetricPanel(self.parent, qc_metric))

    def set_notes(self, event):
        self.data.notes = event.new
        self.parent.set_dirty()

    def panel(self):
        """Build a Panel object representing this Evaluation"""
        objects = []
        for metric in self.metrics:
            objects.append(metric.panel())

        allow_failing_str = "Metrics are allowed to fail in this evaluation." if self.data.allow_failed_metrics else ""

        md = f"""
{md_style(12, self.data.description if self.data.description else "*no description provided*")}
{md_style(8, f"Current state: **{status_html(self.data.status)}**")}
{md_style(8, f"Contains **{len(self.data.metrics)}** metrics. {allow_failing_str}")}
"""
        
        header = pn.pane.Markdown(md)

        notes = pn.widgets.TextAreaInput(
            name="Notes:",
            value=self.data.notes, placeholder="no notes provided"
        )

        notes.param.watch(self.set_notes, "value")

        header_row = pn.Row(header, notes)

        accordion = pn.Accordion(*objects, sizing_mode='stretch_width')
        accordion.active = [0]

        col = pn.Column(header_row, accordion, name=self.data.name)

        return col
