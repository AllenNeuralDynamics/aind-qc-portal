"""Panels for the Portal app"""

from datetime import datetime, timedelta
import panel as pn
from panel.custom import PyComponent
from aind_qc_portal.layout import OUTER_STYLE, AIND_COLORS
from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.assets.asset_group import AssetGroup
from aind_qc_portal.portal.settings import settings

RECORD_LIMIT = 500
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

        self.settings = settings

        # Import modal and create gear button
        self.gear_button = self.settings.panel.create_button(
            action="toggle",
            icon="settings",
            button_type="primary",
            styles={
                "position": "fixed",
                "top": "5px",
                "right": "5px",
                "width": "30px",
                "height": "30px",
                "zIndex": "1000",
                "background": "#fff",
                "borderRadius": "50%",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.15)",
            },
        )

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
        self.submit_button = pn.widgets.Button(
            name="Submit",
            button_type="primary",
            on_click=self._update_asset_group_query,
        )
        self.query_size = pn.widgets.StaticText(
            name="Query returns:",
            value="0 assets",
        )

        # Watch for changes in project_selector and trigger update
        self.project_selector.param.watch(self.update_subject_selector, "value")
        self.project_selector.param.watch(self.update_time_selectors, "value")

        # Watch for changes in selectors and update query count
        self.project_selector.param.watch(self.update_query_count, "value")
        self.subject_selector.param.watch(self.update_query_count, "value")
        self.start_date_selector.param.watch(self.update_query_count, "value")
        self.end_date_selector.param.watch(self.update_query_count, "value")

        self.selectors_col = pn.Column(
            self.project_selector,
            self.subject_selector,
            self.start_date_selector,
            self.end_date_selector,
        )
        self.submit_col = pn.Column(
            self.submit_button,
            self.query_size,
        )

        self.filter_row = pn.Row(
            pn.HSpacer(),
            pn.Row(
                self.selectors_col,
                self.submit_col,
                styles=OUTER_STYLE,
            ),
            pn.HSpacer(),
            self.settings,
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

        # Overlay gear button in top right
        self.panel = pn.Column(
            pn.Row(
                pn.Spacer(),
                self.gear_button,
                styles={"height": "0px"},
            ),
            self.filter_row,
            self.asset_col,
        )

    def update_query_count(self, event=None):

        self.query_size.loading = True
        self.submit_button.disabled = True
        query = self._get_query()
        ids = self.database.get_ids(query) if query else []

        self.query_size.value = f"{len(ids)} assets"

        if len(ids) > RECORD_LIMIT:
            time_estimate = (len(ids) / 100) * 10
            if time_estimate < 60:
                time_estimate_str = "up to a minute"
            else:
                time_estimate_str = "several minutes"
            pn.state.notifications.error(
                f"Query returned {len(ids)} records. Loading this many assets could take {time_estimate_str}. Please refine your query.",
                duration=10000,
            )
        self.query_size.loading = False
        self.submit_button.disabled = False

    def _get_query(self):
        """Get the updatd query"""
        self.database.build_query(
            project_name=self.project_selector.value if self.project_selector.value else None,
            subject_id=self.subject_selector.value if self.subject_selector.value else None,
            start_date=self.start_date_selector.value if self.start_date_selector.value else None,
            end_date=self.end_date_selector.value if self.end_date_selector.value else None,
        )

    def _update_asset_group_query(self, event=None):
        """Update the asset group query based on the selected filters"""

        query = self._get_query()
        print("New query:", query)
        self.asset_group.update_query(query)

    def update_subject_selector(self, event=None):
        """Update the subject selector based on the selected project"""
        print("Updating subject selector...")

        if self.project_selector.value:
            cur_value = self.subject_selector.value
            self.subject_selector.options = self.database.get_subject_ids(project_names=self.project_selector.value)
            if cur_value in self.subject_selector.options:
                self.subject_selector.value = cur_value
        else:
            self.subject_selector.options = self.database.get_subject_ids()

    def update_time_selectors(self, event=None):
        """Update the time selector based on the selected subject"""
        print("Updating time selector...")

        if self.project_selector.value:
            # Get the min and max acquisition start times for the selected project
            min_time, max_time = self.database.get_acquisition_time_range(project_names=self.project_selector.value)
            print(("Min time:", min_time, "Max time:", max_time))

            self.start_date_selector.disabled = False
            self.end_date_selector.disabled = False
        else:
            self.start_date_selector.disabled = True
            self.end_date_selector.disabled = True

    def __panel__(self):
        """Return the Panel representation of the Portal app"""
        return self.panel
