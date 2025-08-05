"""QC View main entrypoint"""

import altair as alt
import panel as pn
import param

# Setup Panel and Altair
from aind_qc_portal.panel.quality_control import QCPanel
from aind_qc_portal.utils import format_css_background
from aind_qc_portal.view.database import get_qc_df_from_name
from aind_qc_portal.view.panel import QCPanel


alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor")

format_css_background()


# State sync
class Settings(param.Parameterized):
    """Top-level settings for QC app"""

    name = param.String(default="multiplane-ophys_721291_2024-04-26_08-05-27_processed_2025-03-01_02-55-21", allow_None=True)


settings = Settings()
pn.state.location.sync(settings, {"location": "location"})

qc_data = get_qc_df_from_name(settings.name)
qc_panel = QCPanel(name=settings.name, data=qc_data)

qc_panel.panel().servable(title="AIND QC - View")
