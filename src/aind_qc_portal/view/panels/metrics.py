import pandas as pd
import panel as pn
from panel.custom import PyComponent
from typing import Any, Callable

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.view.panels.media.media import Media
from aind_qc_portal.view.panels.settings import Settings

from aind_qc_portal.utils import OUTER_STYLE, df_scalar_to_list, replace_markdown_with_html


class MetricMedia(PyComponent):

    def __init__(self, reference: str):
        super().__init__()
        self.reference = reference
        self.media = Media(reference, self)


class MetricValue(PyComponent):    

    def __init__(self, name: str, description: str, value: Any, status: Any, callback: Callable):
        super().__init__()
        self.name = name
        self.description = description
        self.value = value
        self.status = status
        self.callback = callback

    def set_value(self, new_value):
        """Set the value of the metric and trigger the callback"""
        self.value = new_value
        self.callback(metric_name=self.name, column_name="value", value=new_value)
    
    def set_status(self, new_status):
        """Set the status of the metric and trigger the callback"""
        self.status = new_status
        self.callback(metric_name=self.name, column_name="status", value=new_status)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.auto_value = False
        self.auto_state = False

        if isinstance(self.value, bool):
            self.value_widget = pn.widgets.Checkbox(name=name)
        elif not self.value or isinstance(self.value, str):
            self.value_widget = pn.widgets.TextInput(name=name)
        elif isinstance(self.value, float):
            self.value_widget = pn.widgets.FloatInput(name=name)
        elif isinstance(self.value, int):
            self.value_widget = pn.widgets.IntInput(name=name)
        elif isinstance(self.value, list):
            df = pd.DataFrame({"values": self.value})
            self.value_widget = pn.pane.DataFrame(df)
            self.auto_value = True
        elif isinstance(self.value, dict):
            if CustomMetricValue.is_custom_metric(self.value):
                self.value = CustomMetricValue(self.value, self._set_value, self._set_status)
                self.auto_value = True
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
                    self.value_widget = pn.widgets.JSONEditor(name=name)
        else:
            self.value_widget = pn.widgets.StaticText(value=f"Can't deal with type {type(self.value)}")

        self.value_widget.link(self, value="value", bidirectional=True)

    def __panel__(self):
        """Create and return the MetricValue panel"""

        md = f"""
{replace_markdown_with_html(10, f"{self.name}")}
{replace_markdown_with_html(8, self.description if self.description else "*no description provided*")}
"""

        if pn.state.user == "guest":
            self.value_widget.disabled = True

        if not auto_value:
            self.value_widget.value = value
            self.value_widget.param.watch(self.set_value, "value")


        return self.value_widget


class MetricTab(PyComponent):
    """Panel for displaying a single MetricMedia panel and its associated MetricValue panels"""


class Metrics(PyComponent):
    """Panel for displaying the metrics"""

    def __init__(self, data: ViewData, settings: Settings, callback: Callable):
        super().__init__()

        # Initialize some helpers we'll use to map between tags/references/metrics
        self.tag_to_reference = {}
        self.reference_to_media = {}
        self.reference_to_value = {}

        self._init_panel_objects()
        self._construct_metrics(data)

        self.settings = settings
        self.settings.param.watch(self._populate_metrics, 'group_by')

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.tabs = pn.Tabs(styles=OUTER_STYLE)

    def _construct_metrics(self, data: ViewData):
        """Build all MetricValue/MetricMedia panels"""

        for i, row in data.dataframe.iterrows():
            print(row)

            # Handle the metric media
            media_panel = MetricMedia(row['reference'])
            self.reference_to_media[row['reference']] = media_panel

    def _populate_metrics(self, data: ViewData):
        """Populate the metrics tabs with data"""
        # Use the group_by field

    def __panel__(self):
        """Create and return the metrics panel"""

        return self.tabs