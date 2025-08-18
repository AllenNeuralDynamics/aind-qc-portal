import pandas as pd
import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.utils import qc_status_color_css
from aind_qc_portal.view.panels.settings import Settings


class Header(PyComponent):
    """Header for the QC view application"""

    record: param.Dict = param.Dict(default={})
    status: param.DataFrame = param.DataFrame(default=pd.DataFrame())

    def __init__(self, record: dict, status: dict, settings: Settings):
        super().__init__()
        self._init_panel_objects()

        self.record = record
        self.status = status
        self.settings = settings

        # Watch for changes in settings.group_by
        self.settings.param.watch(self._update_status_panel, "group_by")

    def _update_status_panel(self, event):
        """Trigger update when group_by changes"""
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
        header_md = f"""
## {self.record["name"]}
Return to [{self.record.get("data_description", {}).get("project_name")}](todo) | [S3 Link]({self.record.get("location")})
"""
        self.header_text.object = header_md

        return self.header_text

    @pn.depends("status", watch=True)
    def _status_panel(self):
        """Create a table to display the status of the QC metrics"""
        if not self.status.empty:
            status_copy = self.status.copy()

            # Get column names excluding the first column
            # Re-order self.status columns so that the group_by columns are first
            # Make sure the first column stays in place
            if hasattr(self, "settings"):
                new_columns = [self.status.columns[0]]
                new_columns += [col for col in self.status.columns if col in self.settings.group_by]
                new_columns += [
                    col
                    for col in self.status.columns
                    if col not in self.settings.group_by and col != self.status.columns[0]
                ]
                status_copy = status_copy[new_columns]

            def apply_styling(x):
                styles = []
                for i, val in enumerate(x):
                    col_name = status_copy.columns[i]
                    if i == 0:
                        styles.append("")
                    elif col_name in self.settings.group_by:
                        styles.append(qc_status_color_css(val))
                    elif col_name not in self.settings.group_by:
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
