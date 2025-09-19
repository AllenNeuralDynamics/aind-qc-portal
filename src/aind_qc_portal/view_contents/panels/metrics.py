from typing import Any, Callable

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.layout import MARGIN, METRIC_VALUE_WIDTH, OUTER_STYLE
from aind_qc_portal.utils import df_scalar_to_list, replace_markdown_with_html
from aind_qc_portal.view_contents.data import ViewData
from aind_qc_portal.view_contents.panels.media.media import Media
from aind_qc_portal.view_contents.panels.metric.metric import CustomMetricValue
from aind_qc_portal.view_contents.panels.settings import Settings


class MetricMedia(PyComponent):

    def __init__(self, reference: str, s3_bucket: str, s3_prefix: str):
        super().__init__()
        self.reference = reference

        if self.reference:
            self.media = Media(reference, s3_bucket=s3_bucket, s3_prefix=s3_prefix)
        else:
            self.media = None

    def __panel__(self):
        """Create and return the MetricMedia panel"""
        return self.media


class MetricValue(PyComponent):

    value = param.Parameter()
    status = param.String()

    def __init__(self, name: str, description: str, value: Any, status: Any, callback: Callable):
        super().__init__()
        self.metric_name = name
        self.description = description
        self.value = value
        self.status = status
        self.callback = callback

        self._init_panel_objects()

    def set_value(self, new_value):
        """Set the value of the metric and trigger the callback"""
        self.value = new_value

    def set_status(self, new_status):
        """Set the status of the metric and trigger the callback"""
        self.status = new_status

    def _update_value(self):
        """Update the value widget when the value changes"""
        self.callback(metric_name=self.metric_name, column_name="value", value=self.value)

    def _update_status(self):
        """Update the status widget when the status changes"""
        self.callback(metric_name=self.metric_name, column_name="status", value=self.status)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        widget_width = METRIC_VALUE_WIDTH - MARGIN * 4

        self.state_selector = pn.widgets.Select.from_param(
            self.param.status,
            options=["Pass", "Fail", "Pending"],
            name="Metric status",
            width=widget_width,
        )

        self.auto_value = False
        self.auto_state = False

        if isinstance(self.value, bool):
            self.value_widget = pn.widgets.Checkbox(name=self.metric_name, width=widget_width)
        elif not self.value or isinstance(self.value, str):
            self.value_widget = pn.widgets.TextInput(name=self.metric_name, width=widget_width)
            if not isinstance(self.value, str):
                self.value = str(self.value)
        elif isinstance(self.value, float):
            self.value_widget = pn.widgets.FloatInput(name=self.metric_name, width=widget_width)
        elif isinstance(self.value, int):
            self.value_widget = pn.widgets.IntInput(name=self.metric_name, width=widget_width)
        elif isinstance(self.value, list):
            df = pd.DataFrame({"values": self.value})
            self.value_widget = pn.pane.DataFrame(df, width=widget_width)
            self.auto_value = True
        elif isinstance(self.value, dict):
            if CustomMetricValue.is_custom_metric(self.value):
                self.value = CustomMetricValue(self.value, self.set_value, self.set_status)
                self.auto_value = True
                self.auto_state = self.value.auto_state
                self.value_widget = self.value.panel()
            else:
                # first, check if every key/value pair has the same length, if so coerce to a dataframe
                if all([isinstance(v, list) for v in self.value.values()]) and all(
                    [len(v) == len(self.value[list(self.value.keys())[0]]) for v in self.value.values()]
                ):
                    self.auto_value = True
                    df = pd.DataFrame(df_scalar_to_list(self.value))
                    self.value_widget = pn.pane.DataFrame(df)
                # Check if all values are strings, ints, or floats, we can also coerce to a dataframe for this
                elif all(
                    [isinstance(v, str) or isinstance(v, int) or isinstance(v, float) for v in self.value.values()]
                ):
                    self.auto_value = True
                    df = pd.DataFrame(df_scalar_to_list(self.value))
                    self.value_widget = pn.pane.DataFrame(df)
                else:
                    self.value_widget = pn.widgets.JSONEditor(name=self.metric_name, width=widget_width)
        else:
            self.value_widget = pn.widgets.StaticText(
                value=f"Can't deal with type {type(self.value)}", width=widget_width
            )

        if not self.auto_value:
            self.value_widget.link(self, value="value", bidirectional=True)

    def __panel__(self):
        """Create and return the MetricValue panel"""

        md = f"""
{replace_markdown_with_html(10, f"{self.metric_name}")}
{replace_markdown_with_html(8, self.description if self.description else "*no description provided*")}
"""

        if pn.state.user == "guest":
            self.value_widget.disabled = True

        if pn.state.user == "guest":
            self.state_selector.disabled = True
        elif self.auto_state:
            self.state_selector.disabled = True

        if not self.auto_value:
            # The value will not automatically update, so we need to watch for changes
            self.value_widget.value = self.value
            self.value_widget.param.watch(self.set_value, "value")

        col = pn.Column(
            pn.pane.Markdown(md),
            self.value_widget,
            self.state_selector,
            width=METRIC_VALUE_WIDTH,
            styles=OUTER_STYLE,
        )
        return col


class MetricTab(PyComponent):
    """Panel for displaying a single MetricMedia panel and its associated MetricValue panels"""

    def __init__(self, name: str, metric_media: MetricMedia, metric_values: list[MetricValue]):
        super().__init__()
        self.metric_name = name
        self.metric_media = metric_media
        self.metric_values = metric_values
        
    def __panel__(self):
        """Create and return the MetricTab panel"""

        value_col = pn.Column(*self.metric_values, width=METRIC_VALUE_WIDTH + MARGIN)

        # Combine them into a single column
        tab_content = pn.Row(
            value_col,
            self.metric_media,
            sizing_mode="stretch_width",
            name=self.metric_name,
        )

        return tab_content


class Metrics(PyComponent):
    """Panel for displaying the metrics"""

    active_tab = param.Integer(default=0)

    def __init__(self, data: ViewData, settings: Settings, callback: Callable):
        super().__init__()
        self.callback = callback

        pn.state.location.sync(self, {"active_tab": "active_tab"})

        # Initialize some helpers we'll use to map between tags/references/metrics
        self.tag_to_value = {}
        self.value_to_reference = {}
        self.reference_to_media = {}

        self._init_panel_objects()
        self._construct_metrics(data)

        self.settings = settings
        self.settings.param.watch(self._populate_metrics, "group_by")
        self._populate_metrics()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.tabs = pn.Tabs(
            styles=OUTER_STYLE,
            tabs_location="left",
        )

    def _construct_metrics(self, data: ViewData):
        """Build all MetricValue/MetricMedia panels"""

        for _, row in data.dataframe.iterrows():
            # Handle the metric value
            value_panel = MetricValue(
                name=row["name"],
                description=row["description"],
                value=row["value"],
                status=row["status_history"][-1]["status"],
                callback=self.callback,
            )

            # Populate the tag -> value dictionary
            for tag in row["tags"] + [row["modality"]["abbreviation"]]:
                if tag not in self.tag_to_value:
                    self.tag_to_value[tag] = [value_panel]
                else:
                    self.tag_to_value[tag].append(value_panel)

            reference = row["reference"]
            # Populate the value -> reference dictionary
            self.value_to_reference[value_panel] = reference

            # Only re-construct the MediaPanel if it doesn't already exist
            if reference not in self.reference_to_media:
                location = data.record["location"].replace("s3://", "")
                s3_bucket, s3_prefix = location.split("/", 1)
                media_panel = MetricMedia(reference, s3_bucket=s3_bucket, s3_prefix=s3_prefix)
                self.reference_to_media[reference] = media_panel

    def _populate_metrics(self, event=None):
        """Populate the metrics tabs with data

        Use the group_by tags to pull together which references will be shown
        Then group all the value panels by their media reference
        """
        active_list = self.tabs.active
        self.tabs.clear()

        print(f"Populating metrics with group_by: {self.settings.group_by}")

        for tag in self.settings.group_by:
            # Get the value panels, references, and media panels for this tag
            value_panels = self.tag_to_value.get(tag, [])

            # Invert the reference mapping, i.e. calculate the reference_to_value mapping for the subset of values we are using
            reference_to_value = {}
            for value_panel in value_panels:
                reference = self.value_to_reference.get(value_panel, None)
                if reference not in reference_to_value:
                    reference_to_value[reference] = []
                reference_to_value[reference].append(value_panel)

            # Build the accordion contents
            tag_accordion = pn.Accordion(name=tag, active=[0])
            for reference in reference_to_value.keys():
                media_panel = self.reference_to_media[reference]
                value_panels = reference_to_value[reference]
                tab = MetricTab(name=tag, metric_media=media_panel, metric_values=value_panels)

                tag_accordion.append((tab.metric_name, tab))

            self.tabs.append(tag_accordion)

        if len(self.tabs.objects) == 0:
            self.tabs.active = -1
        else:
            self.tabs.active = active_list is not None and active_list < len(self.tabs) and active_list or 0

    def __panel__(self):
        """Create and return the metrics panel"""

        return self.tabs
