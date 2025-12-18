"""Header"""

import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.view_contents.panels.settings import Settings


class Header(PyComponent):
    """Header for the QC view application"""

    record: param.Dict = param.Dict(default={})

    def __init__(self, record: dict, settings: Settings):
        """Initialize Header with record, status, and settings"""
        super().__init__()
        self._init_panel_objects()

        self.record = record
        self.settings = settings

        self.settings.param.watch(self._update_status_panel, "default_grouping")

    def _update_status_panel(self, event):
        """Trigger update when default_grouping changes"""
        self.param.trigger("status")

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.header_text = pn.pane.Markdown()

    @pn.depends("record")
    def _header_panel(self):
        """Create header panel with record information"""
        # Get CO link if available
        other_ids = self.record.get("other_identifiers", {})
        if other_ids and "Code Ocean" in other_ids:
            co_link = (
                '| <a href="https://codeocean.allenneuraldynamics.org/data-assets/'
                f'{other_ids["Code Ocean"][0]}" target="_blank">CO Link</a>'
            )
        else:
            co_link = ""

        project_name = self.record.get("data_description", {}).get("project_name")
        project_link = f"/portal?projects=['{project_name}']"

        modalities = [modality["abbreviation"] for modality in self.record.get("data_description", {}).get("modalities", [])]

        header_md = f"""
## {self.record["name"]}
Modalities: **{', '.join(modalities)}**  
Return to <a href="{project_link}" target="_blank">{project_name}</a> {co_link}
"""  # noqa: W291
        self.header_text.object = header_md

        return self.header_text

    def __panel__(self):
        """Create and return the header layout"""

        content = pn.Column(self._header_panel(), styles=OUTER_STYLE, sizing_mode="stretch_width")

        gear_button_wrapper = pn.Row(
            self.settings,
            styles={
                "position": "absolute",
                "top": "10px",
                "right": "40px",
                "z-index": "1000",
            },
            sizing_mode="fixed",
            width=40,
            height=40,
        )

        return pn.Column(content, gear_button_wrapper, styles={"position": "relative"}, sizing_mode="stretch_width")
