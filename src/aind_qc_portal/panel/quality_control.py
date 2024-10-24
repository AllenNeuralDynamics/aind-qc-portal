# Build a single QCEvaluation panel
import json

import panel as pn
import param
from aind_data_schema.core.quality_control import QualityControl

from aind_qc_portal.docdb.database import qc_from_id, qc_update_to_id
from aind_qc_portal.panel.evaluation import QCEvalPanel
from aind_qc_portal.utils import status_html, update_schema_version, OUTER_STYLE


class QCPanel(param.Parameterized):
    modality_filter = param.String(default="All")
    stage_filter = param.String(default="All")

    def __init__(self, id, **params):
        """Construct the QCPanel object"""
        super().__init__(**params)

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

        if not json_data:
            return

        if "quality_control" in json_data:
            self._has_data = True
        else:
            return
        
        if "data_description" in json_data:
            self.modalities = [modality['abbreviation'] for modality in json_data["data_description"]["modality"]]

        update_schema_version(json_data)

        self.asset_name = json_data["name"]
        try:
            self._data = QualityControl.model_validate_json(json.dumps(json_data["quality_control"]))

            self.stages = []
            # parse stages from QC data
            for evaluation in self._data.evaluations:
                if evaluation.stage not in self.stages:
                    self.stages.append(evaluation.stage)

        except Exception as e:
            self._data = None
            print(f"QC object failed to validate: {e}")
            return

        self.evaluations = []
        self.evaluation_filters = []
        for evaluation in self._data.evaluations:
            self.evaluation_filters.append(
                (evaluation.stage, evaluation.modality.abbreviation)
            )
            self.evaluations.append(
                QCEvalPanel(parent=self, qc_evaluation=evaluation)
            )

    @property
    def data(self):
        return QualityControl(
            evaluations=[eval.data for eval in self.evaluations],
        )

    def set_dirty(self, *event):
        self.submit_button.disabled = False
        self.submit_button.param.trigger('disabled')

    def submit_changes(self, *event):
        qc_update_to_id(self.id, self.data)
        self.submit_button.disabled = True
        self.hidden_html.object = "<script>window.location.reload();</script>"

    def _update_modality_filter(self, event):
        self.modality_filter = event.new

    def _update_stage_filter(self, event):
        self.stage_filter = event.new

    @param.depends('modality_filter', 'stage_filter', watch=True)
    def update_objects(self):
        objects = []
        for evaluation, filters in zip(self.evaluations, self.evaluation_filters):
            (stage, modality) = filters
            if (
                not (self.modality_filter != "All" and modality != self.modality_filter)
                and
                not (self.stage_filter != "All" and stage != self.stage_filter)
            ):
                objects.append(evaluation.panel())

        self.tabs.objects = objects

    def panel(self):
        """Build a Panel object representing this QC action"""
        if not self._has_data:
            return pn.widgets.StaticText(value="No QC object available")

        # build the header
        md = f"""
# Quality control for {self.asset_name}
"""
        header = pn.pane.Markdown(md)

        # build the display box: this shows the current state in DocDB of this asset
        # if any evaluations are failing, we'll show a warning
        failing_eval_str = ""

        state_md = f"""
<span style="font-size:14pt">Current state:</span>
<span style="font-size:12pt">Status: **{status_html(self._data.status)}**</span>
<span style="font-size:12pt">Contains {len(self.evaluations)} evaluations. {failing_eval_str}</span>
"""

        state_pane = pn.pane.Markdown(state_md)

        notes_box = pn.widgets.TextAreaInput(name='Notes:', value=self._data.notes, placeholder="no notes provided")
        notes_box.param.watch(self.set_dirty, "value")

        # state row
        state_row = pn.Row(state_pane, notes_box)
        quality_control_pane = pn.Column(header, state_row)

        # button
        header_row = pn.Row(
            quality_control_pane, pn.HSpacer(), self.submit_button
        )

        # filters for modality and stage
        self.modality_selector = pn.widgets.Select(
            name="Modality",
            options=["All"] + self.modalities,
        )
        self.stage_selector = pn.widgets.Select(
            name="Stage",
            options=["All"] + self.stages,
        )

        self.modality_selector.param.watch(self._update_modality_filter, "value")
        self.stage_selector.param.watch(self._update_stage_filter, "value")

        header_col = pn.Column(header_row, pn.Row(self.modality_selector, self.stage_selector), styles=OUTER_STYLE)

        self.tabs = pn.Tabs(sizing_mode='stretch_width', styles=OUTER_STYLE)
        self.update_objects()

        col = pn.Column(header_col, self.tabs, self.hidden_html)

        return col

    def dump(self):
        """Return this quality_control.json object back to it's JSON format"""
