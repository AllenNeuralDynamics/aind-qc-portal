"""Metrics"""

from typing import Any, Callable

import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param
from panel.custom import PyComponent

from aind_qc_portal.layout import MARGIN, METRIC_VALUE_WIDTH, OUTER_STYLE
from aind_qc_portal.utils import df_scalar_to_list, replace_markdown_with_html
from aind_qc_portal.view_contents.data import ViewData
from aind_qc_portal.view_contents.panels.media.media import Media
from aind_qc_portal.view_contents.panels.metric.metric import CustomMetricValue


WIDGET_WIDTH = METRIC_VALUE_WIDTH - MARGIN * 4


class MetricValue(PyComponent):
    """Panel for displaying a single metric value with status"""

    value = param.Parameter()
    status = param.String()

    def __init__(
        self,
        name: str,
        description: str,
        tags: dict[str, str],
        stage: str,
        modality: str,
        value: Any,
        status: Any,
        callback: Callable,
    ):
        """Initialize MetricValue with metric properties"""
        super().__init__()
        self.metric_name = name
        self.description = description
        self._tags = tags
        self.stage = stage
        self.modality = modality
        self.value = value
        self.status = status
        self.callback = callback

        self._init_panel_objects()

    def set_value(self, new_value):
        """Set the value of the metric and trigger the callback"""
        self.value = new_value

    def set_status(self, new_status):
        """Set the status of the metric and trigger the callback"""
        self.status = new_status

    def _update_value(self):
        """Update the value widget when the value changes"""
        self.callback(metric_name=self.metric_name, column_name="value", value=self.value)

    def _update_status(self):
        """Update the status widget when the status changes"""
        self.callback(metric_name=self.metric_name, column_name="status", value=self.status)

    def _init_dict_objects(self):
        """Helper function for dictionary metric values"""
        if CustomMetricValue.is_custom_metric(self.value):
            self.value = CustomMetricValue(self.value, self.set_value, self.set_status)
            self.auto_value = True
            self.auto_state = self.value.auto_state
            self.value_widget = self.value.panel()
        else:
            # first, check if every key/value pair has the same length, if so coerce to a dataframe
            if all([isinstance(v, list) for v in self.value.values()]) and all(
                [len(v) == len(self.value[list(self.value.keys())[0]]) for v in self.value.values()]
            ):
                self.auto_value = True
                df = pd.DataFrame(df_scalar_to_list(self.value))
                self.value_widget = pn.pane.DataFrame(df)
            # Check if all values are strings, ints, or floats, we can also coerce to a dataframe for this
            elif all([isinstance(v, str) or isinstance(v, int) or isinstance(v, float) for v in self.value.values()]):
                self.auto_value = True
                df = pd.DataFrame(df_scalar_to_list(self.value))
                self.value_widget = pn.pane.DataFrame(df)
            else:
                self.value_widget = pn.widgets.JSONEditor(name=self.metric_name, width=WIDGET_WIDTH)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.state_selector = pn.widgets.Select.from_param(
            self.param.status,
            options=["Pass", "Fail", "Pending"],
            name="Metric status",
            width=WIDGET_WIDTH,
        )

        self.auto_value = False
        self.auto_state = False

        if isinstance(self.value, bool):
            self.value_widget = pn.widgets.Checkbox(name=self.metric_name, width=WIDGET_WIDTH)
        elif not self.value or isinstance(self.value, str):
            self.value_widget = pn.widgets.TextInput(name=self.metric_name, width=WIDGET_WIDTH)
            if not isinstance(self.value, str):
                self.value = str(self.value)
        elif isinstance(self.value, float):
            self.value_widget = pn.widgets.FloatInput(name=self.metric_name, width=WIDGET_WIDTH)
        elif isinstance(self.value, int):
            self.value_widget = pn.widgets.IntInput(name=self.metric_name, width=WIDGET_WIDTH)
        elif isinstance(self.value, list):
            df = pd.DataFrame({"values": self.value})
            self.value_widget = pn.pane.DataFrame(df, width=WIDGET_WIDTH)
            self.auto_value = True
        elif isinstance(self.value, dict):
            self._init_dict_objects()
        else:
            self.value_widget = pn.widgets.StaticText(
                value=f"Can't deal with type {type(self.value)}", width=WIDGET_WIDTH
            )

        if not self.auto_value:
            self.value_widget.link(self, value="value", bidirectional=True)

    def __panel__(self):
        """Create and return the MetricValue panel"""

        tags_display = " | ".join([f"{k}: **{v}**" for k, v in self._tags.items()]) if self._tags else "*no tags*"

        md = f"""
**{replace_markdown_with_html(10, f"{self.metric_name}")}**  
*{replace_markdown_with_html(8, self.description if self.description else "*no description provided*")}*

Modality: **{self.modality}** | Stage: **{self.stage}**  
Tags: {tags_display}
"""  # noqa: W291

        if pn.state.user == "guest":
            self.value_widget.disabled = True

        if pn.state.user == "guest":
            self.state_selector.disabled = True
        elif self.auto_state:
            self.state_selector.disabled = True

        if not self.auto_value:
            # The value will not automatically update, so we need to watch for changes
            self.value_widget.value = self.value
            self.value_widget.param.watch(self.set_value, "value")

        col = pn.Column(
            pn.pane.Markdown(md),
            self.value_widget,
            self.state_selector,
            width=METRIC_VALUE_WIDTH,
            styles=OUTER_STYLE,
        )
        return col


class MetricTab(PyComponent):
    """Panel for displaying a single MetricMedia panel and its associated MetricValue panels"""

    def __init__(self, name: str, metric_media: Media, metric_values: list[MetricValue]):
        """Initialize MetricTab with name, media, and values"""
        super().__init__()
        self.tab_name = name
        self.tab_media = metric_media
        self.tab_values = metric_values

    def __panel__(self):
        """Create and return the MetricTab panel"""
        value_col = pn.Column(*self.tab_values, width=METRIC_VALUE_WIDTH + MARGIN)
        tab_content = pn.Row(
            value_col,
            self.tab_media,
            sizing_mode="stretch_width",
            name=self.tab_name,
        )
        return tab_content


def build_tree_level(grouping_levels, metrics, metric_lookup_callback, level_idx, path_prefix=""):
    if level_idx >= len(grouping_levels):
        return None

    # tag_keys can be a string ('operational') or tuple ('tag1', 'tag2')
    level_keys = grouping_levels[level_idx]
    if isinstance(level_keys, str):
        tag_keys = [level_keys]
    elif isinstance(level_keys, tuple):
        tag_keys = list(level_keys)
    else:
        tag_keys = level_keys

    level_data = {}

    for row in metrics:
        metric_tags = row.get("tags", {})
        print(metric_tags)

        for tag_key in tag_keys:
            tag_value = metric_tags.get(tag_key)
            if tag_value:
                key = (tag_key, tag_value)
                if key not in level_data:
                    level_data[key] = []
                level_data[key].append(row)

    nodes = []
    for (tag_key, tag_value), tag_metrics in level_data.items():
        node_id = f"{path_prefix}{tag_key}:{tag_value}"
        children = build_tree_level(grouping_levels, tag_metrics, metric_lookup_callback, level_idx + 1, f"{node_id}/")

        node = {"label": f"{tag_key}: {tag_value} ({len(tag_metrics)})", "metric_rows": tag_metrics}

        if children:
            node["items"] = children
        else:
            metric_lookup_callback[node_id] = tag_metrics

        nodes.append(node)

    return nodes if nodes else None


class Metrics(PyComponent):
    """Panel for displaying the metrics"""

    def __init__(self, data: ViewData, callback: Callable, settings):
        """Initialize Metrics with data and callback"""
        super().__init__()
        self.callback = callback
        self.data = data
        self.settings = settings
        self.metric_lookup = {}
        self.media_cache = {}

        self._init_panel_objects()
        self._build_tree()

        self.settings.param.watch(self._on_grouping_change, "default_grouping")

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.tree = pmui.Tree(
            name="Metrics Tree",
            styles=OUTER_STYLE,
            active=[],
            max_width=300,
            sizing_mode="stretch_height",
        )

        self.content_panel = pn.Column(
            pn.pane.Markdown("*Select a metric from the tree*"),
            sizing_mode="stretch_both",
            styles=OUTER_STYLE,
        )

        self.tree.param.watch(self._on_tree_selection, "active")

    def _on_grouping_change(self, event):
        """Rebuild tree when default_grouping changes"""
        self._build_tree()

    def _build_tree(self):
        """Build tree structure based on default_grouping tags"""
        grouping_levels = self.settings.default_grouping

        all_metrics = [row for _, row in self.data.dataframe.iterrows()]
        tree_nodes = build_tree_level(grouping_levels, all_metrics, self.metric_lookup, 0)

        def print_tree(nodes, indent=0):
            if not nodes:
                return
            for node in nodes:
                print("  " * indent + node.get("label", ""))
                if "items" in node:
                    print_tree(node["items"], indent + 1)

        self.tree.items = tree_nodes if tree_nodes else []

        def collect_all_paths(nodes, current_path=()):
            paths = []
            for idx, node in enumerate(nodes):
                node_path = current_path + (idx,)
                if "items" in node and node["items"]:
                    paths.append(node_path)
                    paths.extend(collect_all_paths(node["items"], node_path))
            return paths

        if tree_nodes:
            all_paths = collect_all_paths(tree_nodes)
            self.tree.expanded = all_paths

    def _on_tree_selection(self, event):
        """Handle tree selection changes"""
        if not event.new or len(event.new) == 0:
            return

        selected_item = self.tree.value[0] if self.tree.value else None
        if not selected_item:
            return

        metric_rows = selected_item.get("metric_rows", [])
        if not metric_rows:
            return

        reference_to_values = {}
        for row in metric_rows:
            reference = row.get("reference")

            value_panel = MetricValue(
                name=row["name"],
                description=row["description"],
                value=row["value"],
                tags=row["tags"],
                stage=row["stage"],
                modality=row["modality"]["abbreviation"],
                status=row["status_history"][-1]["status"],
                callback=self.callback,
            )

            if reference not in reference_to_values:
                reference_to_values[reference] = []
            reference_to_values[reference].append(value_panel)

        tabs = []
        for reference, value_panels in reference_to_values.items():
            if reference not in self.media_cache:
                media_panel = Media(
                    reference,
                    s3_bucket=self.data.s3_bucket,
                    s3_prefix=self.data.s3_prefix,
                    raw_s3_loc=self.data.raw_s3_location,
                    lazy_load=True,
                )
                self.media_cache[reference] = media_panel
            else:
                media_panel = self.media_cache[reference]

            if not media_panel.loaded:
                media_panel.load()

            tab_name = f"({media_panel.media_type}: {reference})" if reference else "Metrics"
            tab = MetricTab(name=tab_name, metric_media=media_panel, metric_values=value_panels)
            tabs.append((tab.tab_name, tab))

        if tabs:
            accordion = pn.Accordion(*tabs, sizing_mode="stretch_both", active=[0])
            self.content_panel.objects = [accordion]
        else:
            self.content_panel.objects = [pn.pane.Markdown("*No metrics found*")]

    def __panel__(self):
        """Create and return the metrics panel"""
        return pn.Row(
            self.tree,
            self.content_panel,
            sizing_mode="stretch_both",
        )
