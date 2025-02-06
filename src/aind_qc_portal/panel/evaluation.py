import panel as pn
from datetime import datetime, timezone

from aind_data_schema.core.quality_control import QCEvaluation

from aind_qc_portal.panel.metric import QCMetricMediaPanel, QCMetricPanel, QCMetricValuePanel
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
        self.metric_to_media_map = []

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
            # Track mapping
            if metric.reference not in reference_groups:
                # Store the media_panel index in the reference_groups list
                reference_groups[metric.reference] = len(self.media_panels) - 1
                # Store the mapping
                self.metric_to_media_map.append(reference_groups[metric.reference])
            else:
                self.metric_to_media_map.append(reference_groups[metric.reference])

    @property
    def data(self):
        # allow the metrics to update themselves before returning
        self._data.metrics = [metric.data for metric in self.value_panels]

        return self._data

    def set_notes(self, event):
        self._data.notes = event.new
        self.parent.set_submit_dirty()

    def group_metric_panels(self):
        """Group metric panels by reference data"""

        # We need to group together metrics that are matched up to a single reference
        metric_groups = [[]] * len(self.metric_to_media_map)
        for i, map_index in enumerate(self.metric_to_media_map):
            metric_groups[map_index].append(self.value_panels[i])

        return metric_groups

    def panel(self):
        """Build a Panel object representing this Evaluation"""

        objects = []
        metric_groups = self.group_metric_panels()

        for i, group in enumerate(metric_groups):
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
