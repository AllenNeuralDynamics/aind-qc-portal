"""Generic mouse subject panel"""

from typing import Optional
import pandas as pd
import panel as pn
from panel.custom import PyComponent
from aind_qc_portal.portal.settings import settings


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
        
        settings.param.watch(self._update_table, ["show_full_metadata_path"])

        self._init_panel_components()
        self._update_table()  # Initial population of the table

    def _init_panel_components(self):
        """Initialize the components of the RawAssetCard"""
        md = f"""
### Raw asset: {self.asset_name}
"""

        self.table = pn.pane.DataFrame(
            object=None,
            index=False,
        )

        self.header = pn.pane.Markdown(md)

        self.panel = pn.Column(
            self.header,
            self.table,
        )

    def _update_table(self, event=None):
        """Update the table based on current settings"""
        
        if settings.show_full_metadata_path:
            acquisition_str = "Acquisition.acquisition_start_time"
            subject_str = "Subject.subject_id"
            project_str = "DataDescription.project_name"
            genotype_str = "Subject.subject_details.genotype"
        else:
            acquisition_str = "acquisition_start_time"
            subject_str = "subject_id"
            project_str = "project_name"
            genotype_str = "genotype"
        
        self.table.object = pd.DataFrame({
            acquisition_str: [self.acquisition_start_time],
            subject_str: [self.subject_id],
            project_str: [self.project_name],
            genotype_str: [self.genotype],
        })

    def __panel__(self):
        """Return the panel representation of the RawAsetCard"""
        return self.panel
