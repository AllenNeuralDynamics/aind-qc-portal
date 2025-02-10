import panel as pn
from datetime import datetime, timezone

from aind_data_schema.core.quality_control import QCEvaluation

from aind_qc_portal.panel.metric import (
    QCMetricMediaPanel,
    QCMetricPanel,
    QCMetricValuePanel,
)
from aind_qc_portal.utils import replace_markdown_with_html, qc_status_html


class QCEvalPanel:

    def __init__(self, parent, qc_evaluation: QCEvaluation):
        """Build an Evaluation object

        Parameters
        ----------
        parent : QCPanel
        qc_evaluation : QCEvaluation
        """
        self.parent = parent
        self.update(qc_evaluation)

    def update(self, qc_evaluation: QCEvaluation):
        """Update the data in this Evaluation object

        Parameters
        ----------
        qc_evaluation : QCEvaluation
        """

        self._data = qc_evaluation

        self.value_panels = []
        self.media_panels = []
        self.media_to_value_map = []

        # We will split the metric value/reference data into their separate objects
        # We'll also keep a mapping so that metrics that share reference data can be combined
        reference_groups = {}

        for metric in self._data.metrics:
            # Build panel objects
            media_panel = QCMetricMediaPanel(metric, self.parent)
            value_panel = QCMetricValuePanel(metric, self.parent)
            media_panel.register_callback(value_panel._set_value)
            # Register
            self.media_panels.append(media_panel)
            self.value_panels.append(value_panel)
            index = len(self.media_panels) - 1
            # Track mapping
            if metric.reference not in reference_groups:
                # Store the media_panel index in the reference_groups list
                reference_groups[metric.reference] = index
                # Store the mapping
                self.media_to_value_map.append([index])
            else:
                self.media_to_value_map[
                    reference_groups[metric.reference]
                ].append(index)

    @property
    def data(self):
        # allow the metrics to update themselves before returning
        self._data.metrics = [metric.data for metric in self.value_panels]

        return self._data

    def set_notes(self, event):
        self._data.notes = event.new
        self.parent.set_submit_dirty()

    def panel(self):
        """Build a Panel object representing this Evaluation"""

        objects = []

        for i, group_indexes in enumerate(self.media_to_value_map):
            group = [self.value_panels[index] for index in group_indexes]
            objects.append(QCMetricPanel(group, self.media_panels[i]).panel())

        allow_failing_str = (
            "Metrics are allowed to fail."
            if self._data.allow_failed_metrics
            else ""
        )

        md = f"""
{replace_markdown_with_html(12, self._data.description if self._data.description else "*no description provided*")}
{replace_markdown_with_html(8, f"Current state: **{qc_status_html(self._data.status(date=datetime.now(tz=timezone.utc)))}**")}
{replace_markdown_with_html(8, f"Contains **{len(self._data.metrics)}** metrics. {allow_failing_str}")}
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

        accordion = pn.Accordion(
            *objects, sizing_mode="stretch_width", max_height=1200
        )
        accordion.active = [0]

        col = pn.Column(header_row, accordion, name=self._data.name)

        return col
