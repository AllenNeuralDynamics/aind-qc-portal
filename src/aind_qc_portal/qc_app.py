# QC TEST APP

import altair as alt
import panel as pn
import param

alt.data_transformers.disable_max_rows()
# from aind_qc_portal.search import search_bar
from aind_qc_portal.panel.quality_control import QCPanel
from aind_qc_portal.utils import set_background

alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")

set_background()


# State sync
class Settings(param.Parameterized):
    id = param.String(default="a61f285e-c79b-46cd-b554-991d711b6e53")


settings = Settings()
pn.state.location.sync(settings, {"id": "id"})

qc_panel = QCPanel(id=settings.id)

qc_panel.panel().servable(title="AIND QC - View")
