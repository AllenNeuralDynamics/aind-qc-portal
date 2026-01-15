"""Metrics"""

import json
from typing import Any, Callable

import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param
from panel.custom import PyComponent

from aind_qc_portal.layout import WIDGET_WIDTH, METRIC_VALUE_WIDTH, MARGIN, OUTER_STYLE, AIND_COLORS
from aind_qc_portal.utils import df_scalar_to_list, replace_markdown_with_html
from aind_qc_portal.view_contents.data import ViewData, decode_dict_value
from aind_qc_portal.view_contents.panels.media.media import Media
from aind_qc_portal.view_contents.panels.metric.metric import CustomMetricValue
from aind_qc_portal.view_contents.panels.media.curation_apps.curation import GenericCuration, EphysCuration


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
        settings,
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
        self.settings = settings

        self._init_panel_objects()

        # Watch for changes in allow_value_edits
        self.settings.param.watch(self._on_allow_value_edits_change, "allow_value_edits")

        # Watch for changes to value and status to trigger callbacks
        self.param.watch(self._on_value_change, "value")
        self.param.watch(self._on_status_change, "status")

    def set_value(self, new_value):
        """Set the value of the metric and trigger the callback"""
        self.value = new_value

    def set_status(self, new_status):
        """Set the status of the metric and trigger the callback"""
        # Convert Status enum to string if needed
        if hasattr(new_status, "value"):
            new_status = new_status.value
        # Ensure it's a valid status value
        if new_status and new_status not in ["Pass", "Fail", "Pending"]:
            print(f"Warning: Invalid status value '{new_status}', ignoring")
            return
        self.status = new_status

    def _on_value_change(self, event):
        """Called when value changes, triggers callback to submit change"""
        # For CustomMetricValue, we need to compare properly
        # Since CustomMetricValue wraps the actual value, we can't use simple equality
        # Instead, check if both old and new are the same object type
        if isinstance(event.old, CustomMetricValue) and isinstance(event.new, dict):
            # This is the initial setup or a dict update - always process
            should_process = True
        elif isinstance(event.old, dict) and isinstance(event.new, dict):
            # Compare dicts
            should_process = event.new != event.old
        else:
            # For other types, use default comparison
            should_process = event.new != event.old

        if should_process:
            self.callback(metric_name=self.metric_name, column_name="value", value=event.new)

    def _on_status_change(self, event):
        """Called when status changes, triggers callback to submit change"""
        if event.new != event.old:
            self.callback(metric_name=self.metric_name, column_name="status", value=event.new)

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

        # Decode JSON string if present
        decoded_value = self.value
        if isinstance(self.value, str) and self.value.startswith("json:"):
            decoded_value = json.loads(self.value[5:])  # Remove 'json:' prefix and parse
            self.value = decoded_value  # Update self.value with decoded dict

        if isinstance(decoded_value, bool):
            self.value_widget = pn.widgets.Checkbox(name=self.metric_name, width=WIDGET_WIDTH)
        elif not decoded_value or isinstance(decoded_value, str):
            self.value_widget = pn.widgets.TextInput(name=self.metric_name, width=WIDGET_WIDTH)
            if not isinstance(decoded_value, str):
                self.value = str(decoded_value)
        elif isinstance(decoded_value, float):
            self.value_widget = pn.widgets.FloatInput(name=self.metric_name, width=WIDGET_WIDTH)
        elif isinstance(decoded_value, int):
            self.value_widget = pn.widgets.IntInput(name=self.metric_name, width=WIDGET_WIDTH)
        elif isinstance(decoded_value, list):
            df = pd.DataFrame({"values": decoded_value})
            self.value_widget = pn.pane.DataFrame(df, width=WIDGET_WIDTH)
            self.auto_value = True
        elif isinstance(decoded_value, dict):
            self._init_dict_objects()
        else:
            self.value_widget = pn.widgets.StaticText(
                value=f"Can't deal with type {type(decoded_value)}", width=WIDGET_WIDTH
            )

        if not self.auto_value:
            self.value_widget.link(self, value="value", bidirectional=True)

    def _on_allow_value_edits_change(self, event):
        """Update value widget disabled state when allow_value_edits changes"""
        self._update_value_widget_state()

    def _update_value_widget_state(self):
        """Update the disabled state of the value widget based on user and settings"""
        # Disable if user is guest OR if allow_value_edits is False OR if metric has a value
        if isinstance(self.value, CustomMetricValue):
            value = self.value.data.value
        else:
            value = self.value

        should_disable = pn.state.user == "guest" or not self.settings.allow_value_edits or value
        self.value_widget.disabled = should_disable

    def __panel__(self):
        """Create and return the MetricValue panel"""

        tags_display = " | ".join([f"{k}: **{v}**" for k, v in self._tags.items()]) if self._tags else "*no tags*"

        md = f"""
**{replace_markdown_with_html(10, f"{self.metric_name}")}**  
*{replace_markdown_with_html(8, self.description if self.description else "*no description provided*")}*

Modality: **{self.modality}** | Stage: **{self.stage}**  
Tags: {tags_display}
"""  # noqa: W291

        # Update value widget state based on user and settings
        self._update_value_widget_state()

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


class CurationTab(PyComponent):
    """Panel for displaying a curation metric with GenericCuration interface"""

    def __init__(self, name: str, curation_panel: GenericCuration):
        """Initialize CurationTab with name and curation panel"""
        super().__init__()
        self.tab_name = name
        self.curation_panel = curation_panel

    def __panel__(self):
        """Create and return the CurationTab panel"""
        return pn.Column(
            self.curation_panel,
            sizing_mode="stretch_both",
            name=self.tab_name,
        )


def aggregate_status(metrics, status_df):
    """Aggregate status from a list of metrics.

    Rules:
    - If ANY metric has status "Fail", return "Fail"
    - Otherwise, if ANY metric has status "Pending", return "Pending"
    - Otherwise, return "Pass"

    Args:
        metrics: List of metric row dictionaries
        status_df: DataFrame with columns ['name', 'evaluated_status']
    """
    metric_names = [m.get("name") for m in metrics]
    statuses = status_df[status_df["name"].isin(metric_names)]["evaluated_status"].tolist()

    if "Fail" in statuses:
        return "Fail"
    elif "Pending" in statuses:
        return "Pending"
    else:
        return "Pass"


def get_status_color(status):
    """Get the color for a given status"""
    if status == "Fail":
        return AIND_COLORS["red"]
    elif status == "Pending":
        return AIND_COLORS["light_blue"]
    else:  # Pass
        return AIND_COLORS["green"]


def get_tag_keys_from_level(level):
    """Get the tag keys from a grouping level"""
    if isinstance(level, str):
        return [level]
    elif isinstance(level, tuple):
        return list(level)
    else:
        return level


def get_status_icon(status: str):
    """Get the icon name for a given status"""
    if status == "Fail":
        return "cancel"
    elif status == "Pending":
        return "help"
    else:  # Pass
        return "check_circle"


def build_tree_level(grouping_levels, metrics, level_idx, path_prefix="", status_df=None):
    """Recursively build tree levels based on grouping levels and metrics"""
    if level_idx >= len(grouping_levels):
        return None

    level_keys = grouping_levels[level_idx]
    tag_keys = get_tag_keys_from_level(level_keys)

    level_data = {}

    for row in metrics:
        metric_tags = decode_dict_value(row.get("tags", {}))

        for tag_key in tag_keys:
            if tag_key == "stage":
                tag_value = row.get("stage")
            elif tag_key == "modality":
                tag_value = row.get("modality", {}).get("abbreviation")
            else:
                tag_value = metric_tags.get(tag_key)
            if tag_value is not None:
                key = (tag_key, tag_value)
                if key not in level_data:
                    level_data[key] = []
                level_data[key].append(row)
                break

    nodes = []
    for (tag_key, tag_value), tag_metrics in level_data.items():
        node_id = f"{path_prefix}{tag_key}:{tag_value}"
        
        # No need to filter - tag_metrics already contains only rows matching this tag_key:tag_value
        # The grouping logic above already did this filtering
        filtered_metrics = tag_metrics

        children = build_tree_level(grouping_levels, filtered_metrics, level_idx + 1, f"{node_id}/", status_df)

        if children:
            node_metrics = []
            for child in children:
                node_metrics.extend(child.get("metric_rows", []))
        else:
            node_metrics = filtered_metrics

        aggregated_status = aggregate_status(node_metrics, status_df) if status_df is not None else "Pending"

        node = {
            "id": node_id,
            "label": f"{tag_key}: {tag_value} ({len(node_metrics)})",
            "icon": get_status_icon(aggregated_status),
            "metric_rows": node_metrics,
            "status": aggregated_status,
        }

        if children:
            node["items"] = children

        nodes.append(node)

    return nodes if nodes else None


def collect_all_paths(nodes, current_path=()):
    """Helper function to collect all expandable paths"""
    paths = []
    for idx, node in enumerate(nodes):
        node_path = current_path + (idx,)
        if "items" in node and node["items"]:
            paths.append(node_path)
            paths.extend(collect_all_paths(node["items"], node_path))
    return paths


def get_parent_paths(target_tuple):
    """Get paths to expand (all parents of target, but not target itself)"""
    paths = []
    for i in range(1, len(target_tuple)):
        paths.append(target_tuple[:i])
    return paths


class Metrics(PyComponent):
    """Panel for displaying the metrics"""

    active_path = param.String(default="")

    def __init__(self, data: ViewData, callback: Callable, settings):
        """Initialize Metrics with data and callback"""
        super().__init__()
        self._submit_change_callback = callback  # Store the original callback
        self.callback = self._handle_change  # Use wrapper for all metric callbacks
        self.data = data
        self.settings = settings
        self.media_cache = {}
        self._syncing = False

        self._init_panel_objects()
        self._build_tree()

        pn.state.location.sync(self, {"active_path": "active_path"})

        self.settings.param.watch(self._on_grouping_change, "default_grouping")

    def _handle_change(self, metric_name: str, column_name: str, value: str):
        """Wrapper for change callback that updates tree icons after submitting changes"""
        # Submit the change to the database
        self._submit_change_callback(metric_name, column_name, value)

        # Update tree icons if this was a status change
        if column_name == "status":
            self._update_tree_icons()

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.tree = pmui.Tree(
            name="Metrics Tree",
            styles=OUTER_STYLE,
            active=[],
            max_width=300,
            # sizing_mode="stretch_height",
        )

        self.content_panel = pn.Column(
            pn.pane.Markdown("*Select a metric from the tree*"),
            sizing_mode="stretch_both",
            styles=OUTER_STYLE,
        )

        self.tree.param.watch(self._on_tree_selection, "active")
        self.param.watch(self._restore_active_from_url, "active_path")

    def _on_grouping_change(self, event):
        """Rebuild tree when default_grouping changes"""
        self._build_tree()

    def _restore_active_from_url(self, event=None):
        """Restore tree selection from URL parameter after tree is built"""
        if self._syncing or not self.active_path or not self.tree.items:
            return

        try:
            path_tuple = eval(self.active_path)
            self._syncing = True
            self.tree.active = [path_tuple]
        except (SyntaxError, ValueError, TypeError):
            return
        finally:
            self._syncing = False

    def _update_active_path_from_tree(self):
        """Update URL parameter when tree selection changes"""
        if self._syncing:
            return

        self._syncing = True
        try:
            if self.tree.active and len(self.tree.active) > 0:
                self.active_path = str(self.tree.active[0])
            else:
                self.active_path = ""
        finally:
            self._syncing = False

    def _build_tree(self):
        """Build tree structure based on default_grouping tags"""
        grouping_levels = self.settings.default_grouping

        all_metrics = [row for _, row in self.data.dataframe.iterrows()]
        tree_nodes = build_tree_level(grouping_levels, all_metrics, 0, status_df=self.data.metric_status)

        self.tree.items = tree_nodes if tree_nodes else []

        if tree_nodes:
            if "active_path" in pn.state.location.query_params:
                try:
                    active_tuple = eval(pn.state.location.query_params["active_path"])
                    self.tree.expanded = get_parent_paths(active_tuple)
                except (SyntaxError, ValueError, TypeError, KeyError):
                    self.tree.expanded = []
            else:
                self.tree.expanded = []

        self._restore_active_from_url()

    def _update_tree_icons(self):
        """Update tree icons based on current metric_status without rebuilding the entire tree"""

        def update_node_recursive(nodes):
            """Recursively update node icons and statuses"""
            if not nodes:
                return

            for node in nodes:
                # Get metrics for this node
                metric_rows = node.get("metric_rows", [])

                if metric_rows:
                    # Recalculate aggregated status
                    aggregated_status = aggregate_status(metric_rows, self.data.metric_status)

                    # Update icon based on status
                    if aggregated_status == "Fail":
                        icon = "cancel"
                    elif aggregated_status == "Pending":
                        icon = "help"
                    else:  # Pass
                        icon = "check_circle"

                    # Update node
                    node["status"] = aggregated_status
                    node["icon"] = icon

                # Recurse into children
                if "items" in node:
                    update_node_recursive(node["items"])

        # Update all nodes in the tree
        if self.tree.items:
            # Save current state
            current_expanded = self.tree.expanded
            current_active = self.tree.active

            current_items = self.tree.items
            update_node_recursive(current_items)
            # Force refresh by reassigning
            self.tree.items = []
            self.tree.items = current_items

            # Restore state
            self.tree.expanded = current_expanded
            self.tree.active = current_active

    def _build_qc_metric_tabs(self, qc_metrics):
        """Build tabs for QC metrics

        Args:
            qc_metrics: List of QC metric row dictionaries

        Returns:
            List of (tab_name, tab) tuples
        """
        tabs = []
        reference_to_values = {}

        for row in qc_metrics:
            reference = row.get("reference")

            value_panel = MetricValue(
                name=row["name"],
                description=row["description"],
                value=decode_dict_value(row["value"]),
                tags=decode_dict_value(row["tags"]),
                stage=row["stage"],
                modality=row["modality"]["abbreviation"],
                status=row["status_history"][-1]["status"],
                callback=self.callback,
                settings=self.settings,
            )

            if reference not in reference_to_values:
                reference_to_values[reference] = []
            reference_to_values[reference].append(value_panel)

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

        return tabs

    def _build_curation_metric_tabs(self, curation_metrics):
        """Build tabs for curation metrics

        Args:
            curation_metrics: List of curation metric row dictionaries

        Returns:
            List of (tab_name, tab) tuples
        """
        tabs = []

        for row in curation_metrics:
            # Parse the value - it's a JSON string containing the curation data
            curation_value = decode_dict_value(row["value"])

            # The value is a list with a single JSON string element
            if not curation_value:
                curation_data = {}
            elif isinstance(curation_value, list) and len(curation_value) > 0:
                curation_data = json.loads(curation_value[-1])
            elif isinstance(curation_value, str):
                curation_data = json.loads(curation_value)
            else:
                curation_data = curation_value

            curation_type = row.get("type", "")
            reference = row.get("reference")
            
            if curation_type == "Spike sorting curation":
                curation_panel = EphysCuration(
                    data=curation_data,
                    bucket=self.data.s3_bucket,
                    prefix=self.data.s3_prefix,
                    raw_s3_loc=self.data.raw_s3_location,
                    reference=reference,
                )
            else:
                curation_panel = GenericCuration(
                    data=curation_data,
                    bucket=self.data.s3_bucket,
                    prefix=self.data.s3_prefix,
                    raw_s3_loc=self.data.raw_s3_location,
                )

            tab_name = row["name"]
            tab = CurationTab(name=tab_name, curation_panel=curation_panel)
            tabs.append((tab.tab_name, tab))

        return tabs

    def _on_tree_selection(self, event):
        """Handle tree selection changes"""
        self._update_active_path_from_tree()

        if not event.new or len(event.new) == 0:
            return

        selected_item = self.tree.value[0] if self.tree.value else None
        if not selected_item:
            return

        metric_rows = selected_item.get("metric_rows", [])
        if not metric_rows:
            return

        self.content_panel.loading = True

        # Separate curation metrics from QC metrics
        curation_metrics = [row for row in metric_rows if row.get("object_type") == "Curation metric"]
        qc_metrics = [row for row in metric_rows if row.get("object_type") == "QC metric"]

        # Build tabs for each metric type
        tabs = []
        if qc_metrics:
            tabs.extend(self._build_qc_metric_tabs(qc_metrics))
        if curation_metrics:
            tabs.extend(self._build_curation_metric_tabs(curation_metrics))

        if tabs:
            if len(tabs) == 1:
                header = pn.pane.Markdown(f"## {tabs[0][0]}")
                self.content_panel.objects = [header, tabs[0][1]]
            else:
                accordion = pn.Accordion(*tabs, sizing_mode="stretch_both", active=[0])
                self.content_panel.objects = [accordion]
        else:
            self.content_panel.objects = [pn.pane.Markdown("*No metrics found*")]

        self.content_panel.loading = False

    def __panel__(self):
        """Create and return the metrics panel"""

        custom_js = f"""
        <script>
        console.log('[TreeColors] Script loaded');
        
        function getAllElementsIncludingShadow(root = document.body) {{
            const elements = [];
            
            function traverse(node) {{
                elements.push(node);
                
                if (node.shadowRoot) {{
                    traverse(node.shadowRoot);
                }}
                
                for (const child of node.children || []) {{
                    traverse(child);
                }}
            }}
            
            traverse(root);
            return elements;
        }}
        
        function applyTreeColors(source) {{
            console.log('[TreeColors] Applying icon colors, triggered by:', source);
            
            const allElements = getAllElementsIncludingShadow();
            
            const icons = allElements.filter(el => 
                el.tagName === 'SPAN' && 
                el.classList && 
                el.classList.contains('material-icons')
            );
            console.log('[TreeColors] Found icons:', icons.length);
            
            let coloredCount = 0;
            
            icons.forEach((icon) => {{
                const iconText = icon.textContent.trim();
                
                let iconColor;
                
                if (iconText === 'check_circle') {{
                    iconColor = '{AIND_COLORS["green"]}';
                }} else if (iconText === 'cancel') {{
                    iconColor = '{AIND_COLORS["red"]}';
                }} else if (iconText === 'help') {{
                    iconColor = '{AIND_COLORS["light_blue"]}';
                }}
                
                if (iconColor) {{
                    icon.style.setProperty('color', iconColor, 'important');
                    coloredCount++;
                }}
            }});
            
            console.log('[TreeColors] Colored', coloredCount, 'icons');
        }}
        
        // Initial application
        applyTreeColors('initial-load');
        
        // Set up debounced reapplication
        let reapplyTimeout;
        function scheduleReapply(reason) {{
            console.log('[TreeColors] scheduleReapply called, reason:', reason);
            clearTimeout(reapplyTimeout);
            reapplyTimeout = setTimeout(() => applyTreeColors('debounced-' + reason), 20);
        }}
        
        // Set up observer with debouncing
        const observer = new MutationObserver(function(mutations) {{
            // Only reapply on meaningful changes
            let shouldReapply = false;
            let reasons = new Set();
            
            mutations.forEach(m => {{
                if (m.type === 'childList') {{
                    shouldReapply = true;
                    reasons.add('childList:' + (m.addedNodes.length > 0 ? 'added' : 'removed'));
                }} else if (m.type === 'characterData') {{
                    shouldReapply = true;
                    reasons.add('characterData');
                }} else if (m.type === 'attributes' && m.attributeName === 'data-expanded') {{
                    shouldReapply = true;
                    reasons.add('attr:data-expanded');
                }}
            }});
            
            if (shouldReapply) {{
                console.log('[TreeColors] MutationObserver triggered:', Array.from(reasons).join(', '));
                scheduleReapply('mutation:' + Array.from(reasons).join(','));
            }}
        }});
        
        // Observe body and all shadow roots
        function setupObservers() {{
            console.log('[TreeColors] setupObservers called');
            observer.observe(document.body, {{
                childList: true,
                subtree: true,
                characterData: true,
                attributes: true,
                attributeFilter: ['data-selected', 'data-expanded']
            }});
            
            // Find and observe all shadow roots
            const allElements = getAllElementsIncludingShadow();
            let newShadowRoots = 0;
            allElements.forEach(el => {{
                if (el.shadowRoot && !el.hasAttribute('data-shadow-observed')) {{
                    el.setAttribute('data-shadow-observed', 'true');
                    observer.observe(el.shadowRoot, {{
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: true
                    }});
                    newShadowRoots++;
                }}
            }});
            if (newShadowRoots > 0) {{
                console.log('[TreeColors] Found and observing', newShadowRoots, 'new shadow roots');
            }}
        }}
        
        setupObservers();
        
        // Re-setup observers periodically to catch new shadow roots
        // setInterval(() => {{
        //     console.log('[TreeColors] Periodic setupObservers check');
        //     setupObservers();
        // }}, 500);
        
        console.log('[TreeColors] Observers set up');
        </script>
        """

        script_pane = pn.pane.HTML(custom_js, width=0, height=0, sizing_mode="fixed")

        return pn.Column(
            pn.Row(
                self.tree,
                self.content_panel,
                sizing_mode="stretch_both",
            ),
            script_pane,
        )
