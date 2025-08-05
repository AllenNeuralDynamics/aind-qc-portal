""" Panel objects for the View app """

import panel as pn


class QCPanel():
    """Panel for displaying QC data"""

    def __init__(self, name, data):
        self.id = name

    def panel(self):
        """Create and return the Panel layout"""
        # Assuming that the QCPanel class has a method to create the panel layout
        return pn.Column(
            pn.pane.Markdown(f"## QC Data for ID: {self.id}"),
            pn.pane.DataFrame(self.qc_data, width=800),
            sizing_mode="stretch_width"
        )