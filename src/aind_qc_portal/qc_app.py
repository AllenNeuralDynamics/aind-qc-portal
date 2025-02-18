"""QC View main entrypoint"""

import altair as alt
import panel as pn
import param

# Setup Panel and Altair
from aind_qc_portal.panel.quality_control import QCPanel
from aind_qc_portal.utils import format_css_background

alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")
pn.state.clear_caches()

format_css_background()


# State sync
class Settings(param.Parameterized):
    """Top-level settings for QC app"""

    id = param.String(default="")


settings = Settings()
pn.state.location.sync(settings, {"id": "id"})

print(settings.id)

qc_panel = QCPanel(id=settings.id)

qc_panel.panel().servable(title="AIND QC - View")
