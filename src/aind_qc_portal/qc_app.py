"""QC View main entrypoint"""

import altair as alt
import panel as pn
import param

# Setup Panel and Altair
from aind_qc_portal.panel.quality_control import QCPanel
from aind_qc_portal.utils import set_background

alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")

set_background()


# State sync
class Settings(param.Parameterized):
    id = param.String(default="0ff3a040-b590-495a-825b-d2424b6ecacc")


settings = Settings()
pn.state.location.sync(settings, {"id": "id"})

qc_panel = QCPanel(id=settings.id)

qc_panel.panel().servable(title="AIND QC - View")
