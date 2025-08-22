"""Panels for the Portal app"""

from datetime import datetime, timedelta
import panel as pn
from panel.custom import PyComponent
from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.assets.asset_group import AssetGroup


AIND_LAUNCH_DATETIME = datetime(2021, 11, 4).date()
TOMORROW = datetime.today().date() + timedelta(days=1)


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
            options=self.database.get_subject_ids(),
        )
        self.start_date_selector = pn.widgets.DatetimePicker(
            name="Min: acquisition.acquisition_start_time",
            value=AIND_LAUNCH_DATETIME,
            enable_time=False,
            disabled=True,
        )
        self.end_date_selector = pn.widgets.DatetimePicker(
            name="Max: acquisition.acquisition_start_time",
            value=TOMORROW,
            enable_time=False,
            disabled=True,
        )

        # Watch for changes in project_selector and trigger update
        self.project_selector.param.watch(self.update_subject_selector, 'value')
        self.project_selector.param.watch(self.update_time_selectors, 'value')

        # Watch for changes in any selector and update the asset group query
        self.project_selector.param.watch(self._update_asset_group_query, 'value')
        self.subject_selector.param.watch(self._update_asset_group_query, 'value')
        self.start_date_selector.param.watch(self._update_asset_group_query, 'value')
        self.end_date_selector.param.watch(self._update_asset_group_query, 'value')

        self.filter_row = pn.Row(
            pn.HSpacer(),
            pn.Column(
                self.project_selector,
                self.subject_selector,
                self.start_date_selector,
                self.end_date_selector,
                styles=OUTER_STYLE,
            ),
            pn.HSpacer(),
        )

        # Build the asset group
        self.asset_group = AssetGroup(query={}, database=self.database)

        self.asset_col = pn.Column(
            self.asset_group,
        )

        self.main_col = pn.Column(
            self.filter_row,
            self.asset_col,
        )

        self.panel = pn.Column(
            self.filter_row,
            self.asset_col,
        )

    def _update_asset_group_query(self, event=None):
        """Update the asset group query based on the selected filters"""

        query = {"data_description.data_level": "derived"}
        if self.project_selector.value:
            query["data_description.project_name"] = {"$in": self.project_selector.value}
        if self.subject_selector.value:
            query["subject.subject_id"] = {"$in": self.subject_selector.value}
        if query and (self.start_date_selector.value or self.end_date_selector.value):
            time_query = {}
            if self.start_date_selector.value:
                time_query["$gte"] = self.start_date_selector.value.isoformat()
            if self.end_date_selector.value:
                time_query["$lte"] = self.end_date_selector.value.isoformat()
            query["acquisition.acquisition_start_time"] = time_query

        print("New query:", query)
        self.asset_group.update_query(query)

    def update_subject_selector(self, event=None):
        """Update the subject selector based on the selected project"""
        print("Updating subject selector...")

        if self.project_selector.value:
            cur_value = self.subject_selector.value
            self.subject_selector.options = self.database.get_subject_ids(
                project_names=self.project_selector.value
            )
            if cur_value in self.subject_selector.options:
                self.subject_selector.value = cur_value
        else:
            self.subject_selector.options = self.database.get_subject_ids()

    def update_time_selectors(self, event=None):
        """Update the time selector based on the selected subject"""
        print("Updating time selector...")

        if self.project_selector.value:
            # Get the min and max acquisition start times for the selected project
            min_time, max_time = self.database.get_acquisition_time_range(
                project_names=self.project_selector.value
            )
            print(("Min time:", min_time, "Max time:", max_time))

            self.start_date_selector.disabled = False
            self.end_date_selector.disabled = False
        else:
            self.start_date_selector.disabled = True
            self.end_date_selector.disabled = True

    def __panel__(self):
        """Return the Panel representation of the Portal app"""
        return self.panel
