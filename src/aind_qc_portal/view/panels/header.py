from panel.custom import PyComponent
import panel as pn
import param
import pandas as pd

from aind_qc_portal.view.panels.settings import Settings
from aind_qc_portal.utils import qc_status_color_css
from aind_qc_portal.layout import OUTER_STYLE


class Header(PyComponent):
    """Header for the QC view application"""

    data: param.Dict = param.Dict(default={})
    status: param.DataFrame = param.DataFrame(default=pd.DataFrame())

    def __init__(self, data: dict, status: dict, settings: Settings):
        super().__init__()
        self._init_panel_objects()

        self.data = data
        self.status = status
        self.settings = settings

    def _init_panel_objects(self):
        """Initialize empty panel objects"""

        self.header_text = pn.pane.Markdown()
        self.status_table = pn.pane.DataFrame(
            index=False,
            escape=False,
        )

    @pn.depends("data", watch=True)
    def _header_panel(self):
        header_md = f"""
## QC for {self.data["name"]}
"""
        self.header_text.object = header_md

        return self.header_text

    @pn.depends("status", watch=True)
    def _status_panel(self):
        """Create a table to display the status of the QC metrics"""
        if not self.status.empty:
            # Get column names excluding the first column
            columns_to_style = self.status.columns[1:]

            styled_df = self.status.style.apply(
                lambda x: [qc_status_color_css(val) if isinstance(val, str) else "" for val in x],
                subset=columns_to_style,
                axis=0
            ).hide(axis="index").set_table_styles([
                {'selector': 'table', 'props': [('border-collapse', 'collapse')]},
                {'selector': 'th, td', 'props': [('border', '1px solid #ddd'), ('padding', '8px')]},
            ])

            self.status_table.object = styled_df
        else:
            self.status_table.object = self.status

        return self.status_table

    def __panel__(self):
        """Create and return the header layout"""

        full_column = pn.Column(
            self._header_panel(),
            self._status_panel(),
            self.settings,
            styles=OUTER_STYLE,
            sizing_mode="stretch_width"
        )
        return full_column
