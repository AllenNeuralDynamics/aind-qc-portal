"""Project-specific views, uses configurations from projects/"""

import panel as pn
import param

from aind_qc_portal.docdb.database import get_project


class ProjectView(param.Parameterized):
    project = param.String(default="smartspim")

    def __init__(self, **params):
        super().__init__(**params)

    def update(self):
        self.data = get_project(self.project)

    def panel(self):
        return pn.widgets.StaticText(value="meow")


project_view = ProjectView()

# Sync state with the URL
pn.state.location.sync(
    project_view,
    {
        "project": "project",
    },
)

project_view.update()

print(project_view.data[0])

project_view.panel().servable()
