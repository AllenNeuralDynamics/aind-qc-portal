import pandas as pd
import panel as pn
from panel.custom import PyComponent
from typing import Any, Callable

import param

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.view.panels.media.media import Media
from aind_qc_portal.view.panels.metric.metric import CustomMetricValue
from aind_qc_portal.view.panels.settings import Settings

from aind_qc_portal.utils import OUTER_STYLE, df_scalar_to_list, replace_markdown_with_html


class MetricMedia(PyComponent):

    def __init__(self, reference: str):
        super().__init__()
        self.reference = reference
        self.media = Media(reference, self)

    def __panel__(self):
        """Create and return the MetricMedia panel"""
        return self.media


class MetricValue(PyComponent):

    value = param.Parameter()

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
        self.callback(metric_name=self.metric_name, column_name="value", value=self.value)

    def set_status(self, new_status):
        """Set the status of the metric and trigger the callback"""
        self.status = new_status
        self.callback(metric_name=self.metric_name, column_name="status", value=new_status)

    # @param.depends('value', watch=True)
    # def _update_value(self):
    #     """Update the value widget when the value changes"""
    #     self.callback(metric_name=self.metric_name, column_name="value", value=self.value)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.auto_value = False
        self.auto_state = False

        if isinstance(self.value, bool):
            self.value_widget = pn.widgets.Checkbox(name=self.metric_name)
        elif not self.value or isinstance(self.value, str):
            self.value_widget = pn.widgets.TextInput(name=self.metric_name)
        elif isinstance(self.value, float):
            self.value_widget = pn.widgets.FloatInput(name=self.metric_name)
        elif isinstance(self.value, int):
            self.value_widget = pn.widgets.IntInput(name=self.metric_name)
        elif isinstance(self.value, list):
            df = pd.DataFrame({"values": self.value})
            self.value_widget = pn.pane.DataFrame(df)
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
                elif all([isinstance(v, str) or isinstance(v, int) or isinstance(v, float) for v in self.value.values()]):
                    self.auto_value = True
                    df = pd.DataFrame(df_scalar_to_list(self.value))
                    self.value_widget = pn.pane.DataFrame(df)
                else:
                    self.value_widget = pn.widgets.JSONEditor(name=self.metric_name)
        else:
            self.value_widget = pn.widgets.StaticText(value=f"Can't deal with type {type(self.value)}")

        self.value_widget.link(self, value="value", bidirectional=True)

    def __panel__(self):
        """Create and return the MetricValue panel"""

        md = f"""
{replace_markdown_with_html(10, f"{self.metric_name}")}
{replace_markdown_with_html(8, self.description if self.description else "*no description provided*")}
"""

        if pn.state.user == "guest":
            self.value_widget.disabled = True

        if not self.auto_value:
            # The value will not automatically update, so we need to watch for changes
            self.value_widget.value = self.value
            self.value_widget.param.watch(self.set_value, "value")

        col = pn.Column(
            pn.pane.Markdown(md),
            self.value_widget,
            width=300,
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

        value_col = pn.Column(*self.metric_values, width=250)

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

    def __init__(self, data: ViewData, settings: Settings, callback: Callable):
        super().__init__()
        self.callback = callback

        # Initialize some helpers we'll use to map between tags/references/metrics
        self.tag_to_reference = {}
        self.reference_to_media = {}
        self.reference_to_value = {}

        self._init_panel_objects()
        self._construct_metrics(data)

        self.settings = settings
        self.settings.param.watch(self._populate_metrics, 'group_by')
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
            reference = row['reference']
            print(row)
            for tag in row['tags'] + [row['modality']['abbreviation']]:
                if tag not in self.tag_to_reference:
                    self.tag_to_reference[tag] = [reference]
                else:
                    self.tag_to_reference[tag].append(reference)

            # Handle the metric media
            media_panel = MetricMedia(reference)
            self.reference_to_media[reference] = media_panel
            
            # Handle the metric value
            value_panel = MetricValue(
                name=row['name'],
                description=row['description'],
                value=row['value'],
                status=row['status_history'][-1],
                callback=self.callback
            )
            
            if reference not in self.reference_to_value:
                self.reference_to_value[reference] = [value_panel]
            else:
                self.reference_to_value[reference].append(value_panel)

    def _populate_metrics(self, event=None):
        """Populate the metrics tabs with data

        Use the group_by tags to pull together which references will be shown
        Then group all the value panels by their media reference
        """
        active_list = self.tabs.active
        self.tabs.clear()

        print(f"Populating metrics with group_by: {self.settings.group_by}")

        for tag in self.settings.group_by:
            # Get the references for this tag
            references = self.tag_to_reference.get(tag, [])

            # Build the accordion contents
            tag_accordion = pn.Accordion(name=tag, active=[0])
            for reference in references:
                media_panel = self.reference_to_media[reference]
                value_panels = self.reference_to_value.get(reference, [])
                tab = MetricTab(name=tag, metric_media=media_panel, metric_values=value_panels)

                tag_accordion.append(tab)

            self.tabs.append(tag_accordion)

        self.tabs.active = active_list is not None and active_list < len(self.tabs) and active_list or 0

    def __panel__(self):
        """Create and return the metrics panel"""

        return self.tabs