"""QC Project App

Generates a view of a single project's asset records and a dataframe with links out to the QC pages

Intended to be the main entry point for a project's data
"""
import panel as pn
import param
from aind_qc_portal.utils import format_css_background
from aind_qc_portal.projects.project_view import ProjectView

pn.extension("vega")

format_css_background()


class Settings(param.Parameterized):
    project_name = param.String(default="Learning mFISH-V1omFISH")


settings = Settings()
pn.state.location.sync(settings, {"project_name": "project_name"})

project_view = ProjectView(settings.project_name)

row = pn.Row(pn.HSpacer(), project_view.panel(), pn.HSpacer())

row.servable(title="AIND QC - Project")
