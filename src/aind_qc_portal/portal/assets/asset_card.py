"""Generic mouse subject panel"""

import panel as pn
from panel.custom import PyComponent


class RawAssetCard(PyComponent):
    """Panel for an individual subject"""

    def __init__(
        self,
        asset_name: str,
        subject_id: str,
        acquisition_start_time: str = "N/A",
        project_name: str = "N/A",
    ):
        """Initialize the RawAssetCard"""
        super().__init__()

        self.asset_name = asset_name
        self.subject_id = subject_id
        self.acquisition_start_time = acquisition_start_time
        self.project_name = project_name
        
        self._init_panel_components()

    def _init_panel_components(self):
        """Initialize the components of the RawAssetCard"""
        md = f"""
### Raw asset: {self.asset_name}

Acquisition.acquisition_start_time: {self.acquisition_start_time}

Subject.subject_id: {self.subject_id}

DataDescription.project_name: {self.project_name}       
"""

        self.header = pn.pane.Markdown(md)

        self.panel = pn.Column(
            self.header,
        )

    def __panel__(self):
        """Return the panel representation of the RawAsetCard"""
        return self.panel
