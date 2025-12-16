"""Header"""

import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.utils import qc_status_color_css
from aind_qc_portal.view_contents.panels.settings import Settings


class Header(PyComponent):
    """Header for the QC view application"""

    record: param.Dict = param.Dict(default={})
    status: param.DataFrame = param.DataFrame(default=pd.DataFrame())

    def __init__(self, record: dict, status: dict, settings: Settings):
        """Initialize Header with record, status, and settings"""
        super().__init__()
        self._init_panel_objects()

        self.record = record
        self.status = status
        self.settings = settings

        self.settings.param.watch(self._update_status_panel, "default_grouping")

    def _update_status_panel(self, event):
        """Trigger update when default_grouping changes"""
        self.param.trigger("status")

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.header_text = pn.pane.Markdown()
        self.status_table = pn.pane.DataFrame(
            index=False,
            escape=False,
        )

    @pn.depends("record")
    def _header_panel(self):
        """Create header panel with record information"""
        # Get CO link if available
        other_ids = self.record.get("other_identifiers", {})
        if other_ids and "Code Ocean" in other_ids:
            co_link = f"| [CO Link](https://codeocean.allenneuraldynamics.org/data-assets/{other_ids["Code Ocean"][0]})"
        else:
            co_link = ""

        project_link = f"portal?projects=['{self.record.get('data_description', {}).get('project_name')}']"

        header_md = f"""
## {self.record["name"]}
Return to [{self.record.get("data_description", {}).get("project_name")}]({project_link}) {co_link}
"""
        self.header_text.object = header_md

        return self.header_text

    @pn.depends("status", watch=True)
    def _status_panel(self):
        """Create a table to display the status of the QC metrics"""
        if not self.status.empty:
            status_copy = self.status.copy()

            if hasattr(self, "settings"):
                all_grouping_keys = [key for level in self.settings.default_grouping for key in level]
                
                new_columns = [self.status.columns[0]]
                new_columns += [col for col in self.status.columns if col in all_grouping_keys]
                new_columns += [
                    col
                    for col in self.status.columns
                    if col not in all_grouping_keys and col != self.status.columns[0]
                ]
                status_copy = status_copy[new_columns]

            def apply_styling(x):
                """Apply styling to status table rows"""
                styles = []
                for i, val in enumerate(x):
                    col_name = status_copy.columns[i]
                    if i == 0:
                        styles.append("")
                    elif col_name in all_grouping_keys:
                        styles.append(qc_status_color_css(val))
                    elif col_name not in all_grouping_keys:
                        styles.append("color: #999; background-color: #f5f5f5")
                return styles

            styled_df = (
                status_copy.style.apply(apply_styling, axis=1)
                .hide(axis="index")
                .set_table_styles(
                    [
                        {"selector": "table", "props": [("border-collapse", "collapse")]},
                        {"selector": "th, td", "props": [("border", "1px solid #ddd"), ("padding", "8px")]},
                    ]
                )
            )

            self.status_table.object = styled_df
        else:
            self.status_table.object = status_copy

        return self.status_table

    def __panel__(self):
        """Create and return the header layout"""

        full_column = pn.Column(
            self._header_panel(), self._status_panel(), self.settings, styles=OUTER_STYLE, sizing_mode="stretch_width"
        )
        return full_column
