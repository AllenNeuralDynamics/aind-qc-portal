"""QC Project App

Generates a view of a single project's asset records and a dataframe with links out to the QC pages

Intended to be the main entry point for a project's data
"""
import panel as pn
import param
from aind_qc_portal.docdb.database import get_project_names
from aind_qc_portal.utils import format_css_background, AIND_COLORS, OUTER_STYLE
from aind_qc_portal.projects.project_view import ProjectView

pn.extension("vega")

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
        self.project_name_selector = pn.widgets.Select(name='Project Name', options=get_project_names(), value=self.project_name)
        self.project_name_selector.link(self, value='project_name')

    @property
    def project_selector(self):
        return self.project_name_selector

    def panel(self):

        header = pn.pane.Markdown("## Settings")

        col = pn.Column(header, self.project_name_selector, css_classes=["sticky"], styles=OUTER_STYLE, width=350)

        return col


settings = Settings()
pn.state.location.sync(settings, {"project_name": "project_name"})  # sync to URL
settings.panel().value = settings.project_name  # also sync to dropdown value

# Build the project view
project_view = ProjectView(project_name=settings.project_name)


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


def update_project_view(project_name):
    """Helper to update project view and return the new panel object
    """
    project_view.update(project_name)

    return project_view.panel()


# Add the header project dropdown list
project_names = get_project_names()

interactive_header = pn.bind(update_header, settings.project_selector)
header = pn.Row(interactive_header, pn.HSpacer(), width=1000, styles=OUTER_STYLE)

interactive_project_view = pn.bind(update_project_view, settings.project_selector)
main_col = pn.Column(header, interactive_project_view, width=1000)
row = pn.Row(pn.HSpacer(), main_col, pn.HSpacer(max_width=10), settings.panel())

row.servable(title="AIND QC - Project")
