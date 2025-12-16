"""Settings"""

import panel as pn
import param
from panel.custom import PyComponent


class Settings(PyComponent):
    """Settings for the QC view application"""

    default_grouping = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        """Initialize Settings with grouping options"""
        super().__init__()

        self.default_grouping = default_grouping
        self.grouping_options = grouping_options
        self.level_widgets = []
        
        pn.state.location.sync(self, {"default_grouping": "default_grouping"})
        
        self._init_modal()

    def _init_modal(self):
        """Initialize the settings modal"""
        modal_content = pn.Column(
            pn.pane.Markdown("## Metric Grouping Levels"),
            pn.pane.Markdown("Configure the hierarchical levels for organizing metrics in the tree."),
            sizing_mode="stretch_width",
        )
        
        self.levels_container = pn.Column(sizing_mode="stretch_width")
        self.add_level_btn = pn.widgets.Button(
            name="+ Add Level",
            button_type="primary",
            width=120,
        )
        self.add_level_btn.on_click(self._add_level)
        
        modal_content.append(self.levels_container)
        modal_content.append(self.add_level_btn)
        
        self.modal = pn.Modal(modal_content)
        
        for level_info in self.level_widgets:
            level_info["widget"].param.watch(self._update_grouping, "value")
        
        self.gear_button = self.modal.create_button(
            action="toggle",
            button_type="light",
            width=40,
            height=40,
            icon="gear",
        )
        
        
        if self.default_grouping:
            for level_keys in self.default_grouping:
                self._create_level_widget(level_keys)
        else:
            self._create_level_widget([])

    def _create_level_widget(self, selected_keys):
        """Create a widget for a single level"""
        level_idx = len(self.level_widgets)
        
        multichoice = pn.widgets.MultiChoice(
            name=f"Level {level_idx}",
            options=self.grouping_options,
            value=list(selected_keys),
            sizing_mode="stretch_width",
        )
        
        remove_btn = pn.widgets.Button(
            name="×",
            button_type="danger",
            width=40,
        )
        remove_btn.on_click(lambda event: self._remove_level(level_idx))
        
        level_row = pn.Row(
            multichoice,
            remove_btn,
            sizing_mode="stretch_width",
        )
        
        self.level_widgets.append({
            "widget": multichoice,
            "row": level_row,
        })
        
        self.levels_container.append(level_row)
        self._update_grouping()

    def _add_level(self, event):
        """Add a new level"""
        self._create_level_widget([])

    def _remove_level(self, level_idx):
        """Remove a level"""
        if level_idx < len(self.level_widgets):
            level_info = self.level_widgets[level_idx]
            self.levels_container.remove(level_info["row"])
            self.level_widgets.pop(level_idx)
            
            for idx, level_info in enumerate(self.level_widgets):
                level_info["widget"].name = f"Level {idx}"
            
            self._update_grouping()

    def _update_grouping(self, *event):
        """Update the default_grouping based on current level widgets"""
        new_grouping = []
        for level_info in self.level_widgets:
            level_keys = level_info["widget"].value
            if level_keys:
                new_grouping.append(level_keys)
        
        self.default_grouping = new_grouping

    def __panel__(self):
        """Create and return the settings panel"""
        return self.gear_button
