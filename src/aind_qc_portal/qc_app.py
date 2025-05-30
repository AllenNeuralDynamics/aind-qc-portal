"""QC View main entrypoint"""

import altair as alt
import panel as pn
import param

# Setup Panel and Altair
from aind_qc_portal.panel.quality_control import QCPanel
from aind_qc_portal.utils import format_css_background
from aind_qc_portal.docdb.database import id_from_name


alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")

format_css_background()


# State sync
class Settings(param.Parameterized):
    """Top-level settings for QC app"""

    id = param.String(default="0ff3a040-b590-495a-825b-d2424b6ecacc")


settings = Settings()
pn.state.location.sync(settings, {"id": "id"})

# Check if the user passed a name instead of an id
if pn.state.location.query_params.get("name"):
    settings.id = id_from_name(pn.state.location.query_params["name"])


qc_panel = QCPanel(id=settings.id)

qc_panel.panel().servable(title="AIND QC - View")
