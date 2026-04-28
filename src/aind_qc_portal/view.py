"""QC View main entrypoint"""

import traceback

import altair as alt
import panel as pn
import param

# Setup Panel and Altair
from aind_qc_portal.layout import OUTER_STYLE
from aind_qc_portal.utils import format_css_background
from aind_qc_portal.view_contents.data import ViewData
from aind_qc_portal.view_contents.panel import QCPanel

alt.data_transformers.disable_max_rows()
pn.extension("vega", "ace", "jsoneditor", "mathjax", "modal", "tabulator")

format_css_background()


# State sync
class Settings(param.Parameterized):
    """Top-level settings for QC app"""

    asset_name = param.String(
        default="unknown"
    )  # for testing: SmartSPIM_753888_2025-05-23_20-10-58_stitched_2025-05-25_00-43-44


settings = Settings()
pn.state.location.sync(settings, {"asset_name": "name"})

loaded = False
try:
    data = ViewData(asset_name=settings.asset_name)

    qc_panel = QCPanel(record_name=settings.asset_name, data=data)
    loaded = True
except Exception:
    qc_panel = pn.pane.Markdown(
        f"# Error loading QC View for asset: {settings.asset_name}\n\n"
        f"**Error details:**\n```\n{traceback.format_exc()}\n```",
        styles=OUTER_STYLE,
    )

if loaded:
    qc_panel.__panel__().servable(title=f"QC View: {settings.asset_name}")
else:
    qc_panel.servable(title="QC View: Error Loading Asset")
