# Build a single QCEvaluation panel
import panel as pn
import param
import json
from aind_qc_portal.panel.metric import QCMetricPanel
from aind_qc_portal.panel.evaluation import QCEvalPanel
from aind_qc_portal.docdb.database import qc_from_id, qc_update_to_id
from aind_qc_portal.utils import md_style, status_html
from aind_data_schema.core.quality_control import QualityControl, QCEvaluation


class QCPanel:
    modality_filter = param.String(default="All")
    stage_filter = param.String(default="All")

    def __init__(self, id):
        """_summary_"""
        self.id = id

        self.submit_button = pn.widgets.Button(
            name="Submit changes", button_type="success",
        )
        pn.bind(self.submit_changes, self.submit_button, watch=True)

        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False

        self._has_data = False

        self.update()

    def update(self):
        self.get_data()
        self.submit_button.disabled = True

    def get_data(self):
        json_data = qc_from_id(self.id)

        if "quality_control" in json_data:
            self._has_data = True
        else:
            return

        if "schema_version" in json_data["quality_control"]:
            json_data["quality_control"]["schema_version"] = QualityControl.model_construct().schema_version

        print(json_data)

        self.name = json_data["name"]
        try:
            self.data = QualityControl.model_validate_json(json.dumps(json_data["quality_control"]))
        except Exception as e:
            self.data = None
            print(f"QC object failed to validate: {e}")

        self.evaluations = []
        for evaluations in self.data.evaluations:
            self.evaluations.append(
                QCEvalPanel(parent=self, evaluation_data=evaluations)
            )

        self.dirty = False

    def set_dirty(self, *event):
        self.dirty = True
        self.submit_button.disabled = False

    def submit_changes(self, *event):
        qc_update_to_id(self.id, self.data)
        self.submit_button.disabled = True
        self.hidden_html.object = "<script>window.location.reload();</script>"

    def panel(self):
        """Build a Panel object representing this QC action"""
        if not self._has_data:
            return pn.pane("No QC object available")

        objects = []
        for evaluation in self.evaluations:
            objects.append(evaluation.panel())

        # build the header
        md = f"""
# Quality control for {self.name}
"""
        header = pn.pane.Markdown(md)

        # build the display box: this shows the current state in DocDB of this asset
        # if any evaluations are failing, we'll show a warning
        failing_eval_str = ""

        state_md = f"""
<span style="font-size:14pt">Current state:</span>
<span style="font-size:12pt">Status: **{status_html(self.data.status)}**</span>
<span style="font-size:12pt">Contains {len(self.evaluations)} evaluations. {failing_eval_str}</span>
"""

        state_pane = pn.pane.Markdown(state_md)

        notes_box = pn.widgets.TextAreaInput(name='Notes:', value=self.data.notes, placeholder="no notes provided")
        notes_box.param.watch(self.set_dirty, "value")

        # state row
        state_row = pn.Row(state_pane, notes_box)
        quality_control_pane = pn.Column(header, state_row)

        # button
        header_row = pn.Row(
            quality_control_pane, pn.HSpacer(), self.submit_button
        )

        tabs = pn.Tabs(sizing_mode='stretch_width')
        tabs.objects = objects

        col = pn.Column(header_row, pn.layout.Divider(), tabs, self.hidden_html)

        body = col
        return body

    def dump(self):
        """Return this quality_control.json object back to it's JSON format"""
