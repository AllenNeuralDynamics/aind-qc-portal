"""Panels for the Portal app"""

import panel as pn
from panel.custom import PyComponent
import param
from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.portal.database import Database


class Portal(PyComponent):

    def __init__(self, database: Database):
        """Initialize the Portal app"""
        super().__init__()
        self.database = database

        project_names = database.get_unique_project_names()
        self._init_panel_components(project_names)

    def _init_panel_components(self, project_names: list):
        """Initialize the components of the Portal app"""

        self.project_selector = pn.widgets.MultiChoice(
            name="data_description.project_name",
            options=project_names,
        )
        self.subject_selector = pn.widgets.MultiChoice(
            name="subject.subject_id",
            options=[],
            disabled=True,
        )

        # Watch for changes in project_selector and trigger update
        self.project_selector.param.watch(self.update_subject_selector, 'value')

        self.main_col = pn.Column(
            self.project_selector,
            self.subject_selector,
            styles=OUTER_STYLE
        )

        self.panel = pn.Row(pn.HSpacer(), self.main_col, pn.HSpacer())

    def update_subject_selector(self, event=None):
        """Update the subject selector based on the selected project"""
        print("Updating subject selector...")

        if self.project_selector.value:
            self.subject_selector.options = self.database.get_subject_ids(
                project_names=self.project_selector.value
            )
            self.subject_selector.disabled = False
        else:
            self.subject_selector.options = []
            self.subject_selector.disabled = True

    def __panel__(self):
        """Return the Panel representation of the Portal app"""
        return self.panel
