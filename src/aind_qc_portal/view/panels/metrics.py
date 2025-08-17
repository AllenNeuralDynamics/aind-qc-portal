import panel as pn
from panel.custom import PyComponent
from typing import Callable

from aind_qc_portal.view.data import ViewData
from aind_qc_portal.view.panels.media.media import Media
from aind_qc_portal.view.panels.settings import Settings

from aind_qc_portal.utils import OUTER_STYLE


class MetricMedia(PyComponent):

    def __init__(self, reference: str):
        super().__init__()
        self.reference = reference
        self.media = Media(reference, self)


class MetricValue(PyComponent):
    """TODO"""

    def __init__(self, value: str):
        super().__init__()
        self.value = value
    
    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        pass


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