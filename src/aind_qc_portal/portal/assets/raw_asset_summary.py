"""Generic mouse subject panel"""

from typing import Optional
import pandas as pd
import panel as pn
from panel.custom import PyComponent


class RawAssetSummary(PyComponent):
    """Panel for an individual subject"""

    def __init__(
        self,
        asset_name: str,
        subject_id: str,
        acquisition_start_time: Optional[str] = None,
        project_name: Optional[str] = None,
        genotype: Optional[str] = None,
    ):
        """Initialize the RawAssetCard"""
        super().__init__()

        self.asset_name = asset_name
        self.subject_id = subject_id
        self.acquisition_start_time = acquisition_start_time
        self.project_name = project_name
        self.genotype = genotype

        self._init_panel_components()

    def _init_panel_components(self):
        """Initialize the components of the RawAssetCard"""
        md = f"""
### Raw asset: {self.asset_name}
"""

        table = pn.pane.DataFrame(
            object=pd.DataFrame({
                "Acquisition.acquisition_start_time": [self.acquisition_start_time],
                "Subject.subject_id": [self.subject_id],
                "DataDescription.project_name": [self.project_name],
                "Subject.subject_details.genotype": [self.genotype],
            }),
            index=False,
        )

        self.header = pn.pane.Markdown(md)

        self.panel = pn.Column(
            self.header,
            table,
        )

    def __panel__(self):
        """Return the panel representation of the RawAsetCard"""
        return self.panel
