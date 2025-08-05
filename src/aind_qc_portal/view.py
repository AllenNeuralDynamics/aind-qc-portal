"""QC View main entrypoint"""

import altair as alt
import panel as pn
import param

# Setup Panel and Altair
from aind_qc_portal.utils import format_css_background
from aind_qc_portal.view.database import ViewData
from aind_qc_portal.view.panel import QCPanel


alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")

format_css_background()


# State sync
class Settings(param.Parameterized):
    """Top-level settings for QC app"""

    name = param.String(default="SmartSPIM_753888_2025-05-23_20-10-58_stitched_2025-05-25_00-43-44")


settings = Settings()
pn.state.location.sync(settings, {"name": "name"})

data = ViewData(name=settings.name)

qc_panel = QCPanel(name=settings.name, data=data)

qc_panel.__panel__().servable(title="AIND QC - View")
