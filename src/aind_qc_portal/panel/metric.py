from aind_qc_portal.s3 import SpikeSorting
from aind_qc_portal.plotting.ecephys import raster_aggregated
from aind_qc_portal.utils import md_style
from aind_data_schema.core.quality_control import Status

import panel as pn
import numpy as np

# Build one QC element
ss = SpikeSorting()

sx = ss.st()
clu = ss.clu()
locs = ss.locs()

sy = np.zeros_like(clu)

for uclu in np.unique(clu):
    index = np.where(clu == uclu)
    sy[index] = locs[uclu, 1]

dmap = raster_aggregated(sx, sy)
drift_map = pn.pane.Vega(dmap, max_width=600)


class QCMetricPanel:

    def __init__(self, parent, metric_data: dict):
        """Build a Metric object, should only be called by Evaluation()

        Parameters
        ----------
        evaluation_data : dict
            See aind_data_schema.core.quality_control Evaluation
        """
        self.data = metric_data
        self.parent = parent
        self.reference_img = None
    
    def set_value(self, event):
        self.data.value = event.new
        self.parent.set_dirty()

    def set_status(self, event):

        self.data.metric_status.status = Status(event.new)
        self.parent.set_dirty()

    def panel(self):
        """Build a Panel object representing this metric object

        Returns
        -------
        _type_
            _description_
        """
        if self.data.reference:
            if self.data.reference == "ecephys-drift-map":
                self.reference_img = ""
            else:
                self.reference_img = (
                    f"Unable to parse {self.reference_img}"
                )
        else:
            self.reference_img = "No references included"

        row = pn.Row(
            self.metric_panel(),
            drift_map,
            name=self.data.name,
        )
        return row

    def metric_panel(self):
        # Markdown header to display current state
        md = f"""
{md_style(10, f"Current state: {self.data.metric_status.status.value}")}
{md_style(8, self.data.description if self.data.description else "*no description provided*")}
{md_style(8, f"Value: {self.data.value}")}
"""
        name = self.data.name
        value = self.data.value

        if isinstance(value, bool):
            value_widget = pn.widgets.Checkbox(name=name)
        elif isinstance(value, str):
            value_widget = pn.widgets.TextInput(name=name)
        elif isinstance(value, float):
            value_widget = pn.widgets.FloatInput(name=name)
        elif isinstance(value, int):
            value_widget = pn.widgets.IntInput(name=name)
        elif isinstance(value, dict):
            value_widget = pn.widgets.JSONEditor(name=name)
        else:
            print(f"Error can't deal with type {type(value)}")

        value_widget.value = value
        value_widget.param.watch(self.set_value, 'value')

        state_selector = pn.widgets.Select(value=self.data.metric_status.status.value, options=["Pass", "Fail", "Pending"], name="Metric status")
        state_selector.param.watch(self.set_status, 'value')

        header = pn.pane.Markdown(md)

        col = pn.Column(header, pn.WidgetBox(value_widget, state_selector))

        return col
