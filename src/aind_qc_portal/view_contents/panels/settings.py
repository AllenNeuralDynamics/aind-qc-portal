"""Settings"""

import panel as pn
import panel_material_ui as pmui
import param
from panel.custom import PyComponent


class Settings(PyComponent):
    """Settings for the QC view application"""

    allow_value_edits = param.Boolean(default=False)
    default_grouping = param.List(default=[])

    def __init__(self, default_grouping: list, grouping_options: list):
        """Initialize Settings with grouping options"""
        super().__init__()

        self.grouping_options = grouping_options
        self.level_widgets = []

        # Sync with URL location first
        pn.state.location.sync(self, {"default_grouping": "default_grouping"})

        # If default_grouping is still empty after sync, use the provided default
        if not self.default_grouping:
            print(f"[Settings.__init__] default_grouping empty after sync, using provided default: {default_grouping}")
            self.default_grouping = default_grouping

        self._init_modal()

    def _init_modal(self):
        """Initialize the settings modal"""
        switch_value_edits = pmui.Switch.from_param(
            self.param.allow_value_edits,
            name="Allow Editing Metric Values",
        )

        modal_content = pn.Column(
            pn.pane.Markdown("## Settings"),
            switch_value_edits,
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

        self.submit_btn = pn.widgets.Button(
            name="Apply Settings",
            button_type="success",
            width=120,
        )
        self.submit_btn.on_click(self._submit_grouping)

        modal_content.append(self.levels_container)
        modal_content.append(pn.Row(self.add_level_btn, self.submit_btn))

        self.modal = pn.Modal(modal_content)

        self.gear_button = self.modal.create_button(
            action="toggle",
            button_type="light",
            width=40,
            height=40,
            icon="settings",
        )

        print(f"[Settings._init_modal] Creating level widgets from default_grouping: {self.default_grouping}")

        if self.default_grouping:
            print(f"[Settings._init_modal] default_grouping is truthy, creating {len(self.default_grouping)} levels")
            for i, level_keys in enumerate(self.default_grouping):
                print(f"[Settings._init_modal] Creating level {i} with keys: {level_keys}")
                self._create_level_widget(level_keys)
        else:
            self._create_level_widget([])

    def _create_level_widget(self, selected_keys):
        """Create a widget for a single level"""
        level_idx = len(self.level_widgets)

        # selected_keys can be a string ('operational') or tuple ('tag1', 'tag2')
        # Convert to list for MultiChoice
        if isinstance(selected_keys, str):
            value_list = [selected_keys]
        elif isinstance(selected_keys, tuple):
            value_list = list(selected_keys)
        else:
            value_list = list(selected_keys) if selected_keys else []

        multichoice = pn.widgets.MultiChoice(
            name=f"Level {level_idx}",
            options=self.grouping_options,
            value=value_list,
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

        self.level_widgets.append(
            {
                "widget": multichoice,
                "row": level_row,
            }
        )

        self.levels_container.append(level_row)

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

    def _submit_grouping(self, *event):
        """Update the default_grouping based on current level widgets when submit is clicked"""

        new_grouping = []
        for i, level_info in enumerate(self.level_widgets):
            level_keys = level_info["widget"].value
            print(f"[Settings._submit_grouping] Level {i} has value: {level_keys}")
            if level_keys:
                # level_keys is a list of strings from MultiChoice
                # If single item, unwrap to string; if multiple, keep as tuple
                if len(level_keys) == 1:
                    new_grouping.append(level_keys[0])
                else:
                    new_grouping.append(tuple(level_keys))

        self.default_grouping = new_grouping

    def __panel__(self):
        """Create and return the settings panel"""

        return pn.Column(
            self.gear_button,
            self.modal
        )
