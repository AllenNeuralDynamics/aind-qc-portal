"""Panels for the Portal app"""

from datetime import datetime, timedelta
import panel as pn
from panel.custom import PyComponent
from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.portal_contents.database import Database
from aind_qc_portal.portal_contents.assets.asset_group import AssetGroup
from aind_qc_portal.portal_contents.settings import settings

RECORD_LIMIT = 20000
AIND_LAUNCH_DATETIME = datetime(2021, 11, 4).date()
TOMORROW = datetime.today().date() + timedelta(days=1)


class Portal(PyComponent):

    def __init__(self, database: Database):
        """Initialize the Portal app"""
        super().__init__()
        self.database = database

        self.previous_query = None

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

        # Create selectors without watchers initially
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

        # Sync selectors to URL parameters
        pn.state.location.sync(self.project_selector, {"value": "projects"})
        pn.state.location.sync(self.subject_selector, {"value": "subjects"})
        pn.state.location.sync(self.start_date_selector, {"value": "start_date"})
        pn.state.location.sync(self.end_date_selector, {"value": "end_date"})

        # Build the asset group
        self.asset_group = AssetGroup(query={}, database=self.database)

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
            self.settings,
            pn.HSpacer(),
            pn.Row(
                self.selectors_col,
                self.submit_col,
                styles=OUTER_STYLE,
            ),
            pn.HSpacer(),
        )

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

        # Attach watchers first
        # Watch for changes in project_selector and trigger update
        self.project_selector.param.watch(self.update_subject_selector, "value")
        self.project_selector.param.watch(self.update_time_selectors, "value")

        # Watch for changes in selectors and update query count
        self.project_selector.param.watch(self.update_query_count, "value")
        self.subject_selector.param.watch(self.update_query_count, "value")
        self.start_date_selector.param.watch(self.update_query_count, "value")
        self.end_date_selector.param.watch(self.update_query_count, "value")

        # Initialize from URL parameters if present, handling dependencies
        # This needs to happen after watchers are attached so they don't fire during setup
        self._initialize_from_url()

    def _initialize_from_url(self):
        """Initialize selectors from URL parameters, handling dependencies"""
        # If projects are specified in URL, update subject options and time ranges
        if self.project_selector.value:
            # Update subject options based on selected projects
            self.subject_selector.options = self.database.get_subject_ids(project_names=self.project_selector.value)

            # Update time ranges and enable date selectors if not already set from URL
            # Only update if the date selectors still have default values
            if self.start_date_selector.value == AIND_LAUNCH_DATETIME or self.end_date_selector.value == TOMORROW:
                min_time, max_time = self.database.get_acquisition_time_range(project_names=self.project_selector.value)
                if min_time and self.start_date_selector.value == AIND_LAUNCH_DATETIME:
                    self.start_date_selector.value = datetime.fromisoformat(min_time).date()
                if max_time and self.end_date_selector.value == TOMORROW:
                    self.end_date_selector.value = datetime.fromisoformat(max_time).date() + timedelta(days=1)

            self.start_date_selector.disabled = False
            self.end_date_selector.disabled = False

            # Update query count and execute query if parameters are present
            self.update_query_count()
            self._update_asset_group_query()

    def _get_query(self):
        """Build the query from the current selector values"""
        query = self.database.build_query(
            project_name=self.project_selector.value if self.project_selector.value else None,
            subject_id=self.subject_selector.value if self.subject_selector.value else None,
            start_date=self.start_date_selector.value if self.start_date_selector.value else None,
            end_date=self.end_date_selector.value if self.end_date_selector.value else None,
        )
        return query

    def update_query_count(self, event=None):
        """Update the number of records that will be returned for a query"""
        query = self._get_query()

        # Don't update query count for the same query twice
        if query == self.previous_query:
            return
        self.previous_query = query

        self.query_size.loading = True
        self.submit_button.disabled = True

        N = self.database.get_query_count(
            project_name=self.project_selector.value if self.project_selector.value else None,
            subject_id=self.subject_selector.value if self.subject_selector.value else None,
            start_date=self.start_date_selector.value if self.start_date_selector.value else None,
            end_date=self.end_date_selector.value if self.end_date_selector.value else None,
        )

        if N > RECORD_LIMIT:
            time_estimate = (N / 1000) * 1
            if time_estimate < 60:
                time_estimate_str = "up to a minute"
            else:
                time_estimate_str = "several minutes"
            pn.state.notifications.error(
                f"Query returned {N} records. Loading this many assets could take {time_estimate_str}. Please refine your query.",
                duration=10000,
            )
        self.query_size.loading = False
        self.submit_button.disabled = False

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
            self.start_date_selector.value = (
                datetime.fromisoformat(min_time).date() if min_time else AIND_LAUNCH_DATETIME
            )
            self.end_date_selector.value = (
                datetime.fromisoformat(max_time).date() + timedelta(days=1) if max_time else TOMORROW
            )

            self.start_date_selector.disabled = False
            self.end_date_selector.disabled = False
        else:
            self.start_date_selector.disabled = True
            self.end_date_selector.disabled = True

    def __panel__(self):
        """Return the Panel representation of the Portal app"""
        return self.panel
