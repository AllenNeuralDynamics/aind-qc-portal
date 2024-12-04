"""Build the Quality Control Panel object"""

import json

import panel as pn
import pandas as pd
import param
from aind_data_schema.core.quality_control import QualityControl

from aind_qc_portal.docdb.database import record_from_id, qc_update_to_id
from aind_data_schema_models.modalities import Modality
from aind_qc_portal.panel.evaluation import QCEvalPanel
from aind_qc_portal.utils import (
    status_html,
    OUTER_STYLE,
)


class QCPanel(param.Parameterized):
    """QualityControl Panel object"""

    modality_filter = param.String(default="All")
    stage_filter = param.String(default="All")

    def __init__(self, id, **params):
        """Construct the QCPanel object"""
        super().__init__(**params)

        self.id = id

        # Set up the submission area
        self.submit_button = pn.widgets.Button(
            name="Submit changes" if pn.state.user != "guest" else "Log in",
            button_type="success",
        )
        self.changes = 0
        self.change_info = pn.widgets.StaticText(
            value=""
        )
        self.submit_info = pn.widgets.StaticText(
            value=(
                f"Logged in as {pn.state.user}"
                if pn.state.user != "guest"
                else "Log in to submit changes"
            )
        )
        self.submit_error = pn.widgets.StaticText(value="")
        self.submit_col = pn.Column(
            self.submit_button, self.change_info, self.submit_info, self.submit_error
        )
        pn.bind(self.submit_changes, self.submit_button, watch=True)

        self.hidden_html = pn.pane.HTML("")
        self.hidden_html.visible = False

        self._has_data = False

        self.update()

    def update(self):
        self.get_data()
        self.submit_button.disabled = pn.state.user != "guest"

    def get_data(self):
        json_data = record_from_id(self.id)

        if not json_data:
            return

        if "quality_control" in json_data:
            self._has_data = True
        else:
            return

        if "data_description" in json_data and json_data["data_description"] and "modality" in json_data["data_description"]:
            self.modalities = [
                Modality.from_abbreviation(modality["abbreviation"])
                for modality in json_data["data_description"]["modality"]
            ]
        else:
            self.modalities = []

        s3_location = json_data.get("location", None)
        if s3_location:
            s3_location = s3_location.replace("s3://", "")
            self.s3_bucket = s3_location.split("/")[0]
            self.s3_prefix = s3_location.split("/")[1]

        self.asset_name = json_data["name"]
        try:
            self._data = QualityControl.model_validate_json(
                json.dumps(json_data["quality_control"])
            )

        except Exception as e:
            self._data = None
            self._has_data = False
            print(f"QC object failed to validate: {e}")
            return

        self.stages = list({evaluation.stage for evaluation in self._data.evaluations})
        self.tags = list({tag for evaluation in self._data.evaluations if evaluation.tags for tag in evaluation.tags})

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
        self.changes += 1
        self.change_info.value = f"{self.changes} pending changes"
        self.submit_button.disabled = False
        self.submit_button.param.trigger("disabled")

    def submit_changes(self, *event):
        """Submit the current state to DocDB"""

        # redirect users to login
        if pn.state.user == "guest":
            self.hidden_html.object = f"<script>window.location.href = '/login?next={pn.state.location.href}';</script>"
            return

        response = qc_update_to_id(self.id, self.data)

        if response.status_code != 200:
            self.submit_error.value = f"Error ({response.status_code}) submitting changes: {response.text}"
            self.submit_button.button_type = "danger"
            return
        else:
            self.submit_button.disabled = True
            self.changes = 0
            self.change_info.value = f"{self.changes} pending changes"
            self.hidden_html.object = (
                "<script>window.location.reload();</script>"
            )

    def _update_modality_filter(self, event):
        self.modality_filter = event.new

    def _update_stage_filter(self, event):
        self.stage_filter = event.new

    @param.depends("modality_filter", "stage_filter", watch=True)
    def update_objects(self):
        objects = []
        for evaluation, filters in zip(
            self.evaluations, self.evaluation_filters
        ):
            (stage, modality) = filters
            if not (
                self.modality_filter != "All"
                and modality != self.modality_filter
            ) and not (
                self.stage_filter != "All" and stage != self.stage_filter
            ):
                objects.append(evaluation.panel())
        self.tabs.objects = objects

    def status_panel(self):
        """Build a Panel table that shows the current status of all evaluations"""
        # We'll loop over stage and modality to build a table

        data = []
        for modality in self.modalities:
            for stage in self.stages:
                data.append(
                    {
                        "Group": modality.abbreviation,
                        "Stage": stage,
                        "Status": status_html(
                            self._data.status(modality=modality, stage=stage)
                        ),
                    }
                )
        for tag in self.tags:
            for stage in self.stages:
                data.append(
                    {
                        "Group": tag,
                        "Stage": stage,
                        "Status": status_html(
                            self._data.status(tag=tag, stage=stage)
                        ),
                    }
                )

        df = pd.DataFrame(data, columns=["Group", "Stage", "Status"])
        print(df)

        # Reshape the DataFrame using pivot_table
        df_squashed = df.pivot_table(
            index="Stage", columns="Group", values="Status", aggfunc="first"
        )

        # Optional: Clean up column names by flattening the MultiIndex if needed
        df_squashed.columns.name = None
        df_squashed.reset_index(inplace=True)

        return pn.pane.DataFrame(df_squashed, index=False, escape=False)

    def panel(self):
        """Build a Panel object representing this QC action"""
        if not self._has_data or not self._data:
            return pn.widgets.StaticText(value="No QC object available")

        # build the header
        md = f"""
<span style="font-size:14pt">Quality control for {self.asset_name}</span>
"""
        header = pn.pane.Markdown(md)

        # build the display box: this shows the current state in DocDB of this asset
        # if any evaluations are failing, we'll show a warning
        failing_eval_str = ""

        def state_panel():
            state_md = f"""
    <span style="font-size:12pt">Current state:</span>
    <span style="font-size:10pt">Status: **{status_html((self._data.status()))}**</span>
    <span style="font-size:10pt">Contains {len(self.evaluations)} evaluations. {failing_eval_str}</span>
    """
            return pn.pane.Markdown(state_md)

        state_pane = pn.bind(lambda: state_panel())

        notes_box = pn.widgets.TextAreaInput(
            name="Notes:",
            value=self._data.notes,
            placeholder="no notes provided",
        )
        if pn.state.user == "guest":
            notes_box.disabled = True
        else:
            notes_box.param.watch(self.set_dirty, "value")

        # state row
        state_row = pn.Row(state_pane, notes_box, self.status_panel())
        quality_control_pane = pn.Column(header, state_row)

        # button
        header_row = pn.Row(
            quality_control_pane, pn.HSpacer(), self.submit_col
        )

        # filters for modality and stage
        self.modality_selector = pn.widgets.Select(
            name="Modality",
            options=["All"] + [mod.abbreviation for mod in self.modalities],
        )
        self.stage_selector = pn.widgets.Select(
            name="Stage",
            options=["All"] + self.stages,
        )

        self.modality_selector.param.watch(
            self._update_modality_filter, "value"
        )
        self.stage_selector.param.watch(self._update_stage_filter, "value")

        header_col = pn.Column(
            header_row,
            pn.Row(self.modality_selector, self.stage_selector),
            styles=OUTER_STYLE,
        )

        self.tabs = pn.Tabs(sizing_mode="stretch_width", styles=OUTER_STYLE, tabs_location="left")
        self.update_objects()

        col = pn.Column(
            header_col, self.tabs, self.hidden_html
        )

        return col

    def dump(self):
        """Return this quality_control.json object back to it's JSON format"""
