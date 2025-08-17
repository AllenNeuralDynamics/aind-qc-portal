import pandas as pd
import panel as pn
from panel.custom import PyComponent
from typing import Callable

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
    """TODO"""

    def __init__(self, name: str, description: str, value: str):
        super().__init__()
        self.name = name
        self.description = description
        self.value = value

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.auto_value = False
        self.auto_state = False

        if isinstance(self.value, bool):
            self.content = pn.widgets.Checkbox(name=name)
        elif not self.value or isinstance(self.value, str):
            self.content = pn.widgets.TextInput(name=name)
        elif isinstance(self.value, float):
            self.content = pn.widgets.FloatInput(name=name)
        elif isinstance(self.value, int):
            self.content = pn.widgets.IntInput(name=name)
        elif isinstance(self.value, list):
            df = pd.DataFrame({"values": self.value})
            self.content = pn.pane.DataFrame(df)
            self.auto_value = True
        elif isinstance(self.value, dict):
            if CustomMetricValue.is_custom_metric(self.value):
                self.value = CustomMetricValue(self.value, self._set_value, self._set_status)
                self.auto_value = True
                self.content = self.value.panel()
            else:
                # first, check if every key/value pair has the same length, if so coerce to a dataframe
                if all([isinstance(v, list) for v in self.value.values()]) and all(
                    [len(v) == len(self.value[list(self.value.keys())[0]]) for v in self.value.values()]
                ):
                    self.auto_value = True
                    df = pd.DataFrame(df_scalar_to_list(self.value))
                    self.content = pn.pane.DataFrame(df)
                # Check if all values are strings, ints, or floats, we can also coerce to a dataframe for this
                elif all([isinstance(v, str) or isinstance(v, int) or isinstance(v, float) for v in self.value.values()]):
                    self.auto_value = True
                    df = pd.DataFrame(df_scalar_to_list(self.value))
                    self.content = pn.pane.DataFrame(df)
                else:
                    self.content = pn.widgets.JSONEditor(name=name)
        else:
            self.content = pn.widgets.StaticText(value=f"Can't deal with type {type(self.value)}")

    def __panel__(self):
        """Create and return the MetricValue panel"""

        md = f"""
{replace_markdown_with_html(10, f"{self.name}")}
{replace_markdown_with_html(8, self.description if self.description else "*no description provided*")}
"""

        if pn.state.user == "guest":
            self.content.disabled = True

        if not auto_value:
            self.content.value = value
            self.content.param.watch(self.set_value, "value")


        return self.content


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