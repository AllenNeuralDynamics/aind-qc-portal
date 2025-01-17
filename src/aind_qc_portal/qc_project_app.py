"""QC Project App

Generates a view of a single project's asset records and a dataframe with links out to the QC pages

Intended to be the main entry point for a project's data
"""

import panel as pn
import param
from aind_qc_portal.docdb.database import get_project_names
from aind_qc_portal.projects.dataset import ProjectDataset
from aind_qc_portal.utils import (
    format_css_background,
    AIND_COLORS,
    OUTER_STYLE,
)
from aind_qc_portal.projects.project_view import ProjectView
from aind_qc_portal.projects.dataset import ALWAYS_COLUMNS

pn.extension("vega", "tabulator")

format_css_background()

sticky_css = """
.sticky {
    position: sticky;
    top: 10px; /* Distance from the top of the viewport */
    right: 10px; /* Distance from the right of the viewport */
    margin-left: auto;
    z-index: 1000; /* Ensure it stays above other elements */
    background: white;
    border: 1px solid #ccc;
    padding: 10px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
}
"""
pn.config.raw_css.append(sticky_css)


# Set up project name settings and sync to URL
class Settings(param.Parameterized):
    project_name = param.String(default="Learning mFISH-V1omFISH")

    def __init__(self, **params):
        super().__init__(**params)

        self.project_name_selector = pn.widgets.Select(
            name="Project Name", options=get_project_names()
        )
        self.project_name_selector.link(self, value="project_name")

    def panel(self):

        header = pn.pane.Markdown("## Settings")

        col = pn.Column(
            header,
            self.project_name_selector,
        )

        return col


settings = Settings()
pn.state.location.sync(
    settings,
    {
        "project_name": "project_name",
    },
)

settings.project_name_selector.value = (
    settings.project_name
)  # also sync to dropdown value
project_name_original = settings.project_name

# Build the project view
dataset = ProjectDataset(project_name=settings.project_name)
project_view = ProjectView(project_name=settings.project_name, dataset=dataset)

pn.state.location.sync(
    dataset,
    {
        "subject_filter": "subject_filter",
        "derived_filter": "derived_filter",
        "columns_filter": "columns_filter",
        "type_filter": "type_filter",
        "status_filter": "status_filter",
    },
)
dataset.subject_selector.value = dataset.subject_filter
dataset.derived_selector.value = dataset.derived_filter
dataset.columns_selector.value = [
    column
    for column in dataset.columns_filter
    if column not in ALWAYS_COLUMNS
]
dataset.type_selector.value = dataset.type_filter
dataset.status_selector.value = dataset.status_filter


def update_header(project_name):
    # Build the header (depends on some project view data)
    md = f"""
    <h1 style="color:{AIND_COLORS["dark_blue"]};">
        {project_name}
    </h1>
    Project has <b>{project_view.get_asset_count()}</b> data assets.
    """

    header_md_pane = pn.pane.Markdown(md)
    return header_md_pane


hidden_html = pn.pane.HTML("")


def refresh(project_name):
    """Helper to update project view and return the new panel object"""
    if project_name != project_name_original:
        hidden_html.object = "<script>window.location.reload();</script>"
    return hidden_html


# Add the header project dropdown list
project_names = get_project_names()

interactive_header = pn.bind(update_header, settings.project_name_selector)
header = pn.Row(
    interactive_header, pn.HSpacer(), width=990, styles=OUTER_STYLE
)

setting_panel = settings.panel()

interactive_refresh = pn.bind(
    refresh, project_name=settings.project_name_selector
)

main_col = pn.Column(
    header, project_view.panel(), interactive_refresh, width=1000
)

side_col = pn.Column(
    setting_panel,
    dataset.panel(),
    css_classes=["sticky"],
    styles=OUTER_STYLE,
    width=350,
)

row = pn.Row(pn.HSpacer(), main_col, pn.HSpacer(max_width=10), side_col)

row.servable(title="AIND QC - Project")
