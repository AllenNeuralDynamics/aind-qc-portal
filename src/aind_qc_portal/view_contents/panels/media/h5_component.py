

from panel.custom import PyComponent

import h5py
import panel as pn
import param
import numpy as np
from PIL import Image

class H5Component(PyComponent):
    """ Panel component to visualize z-slices of 3d data stored in an H5 file with max projection.

    Args:
        file_path (str): Path to the H5 file containing the 3D volume data.

    Attributes:
        z (int): Current z slice index (center of max projection).
        window (int): Half-window size for max projection.
    """

    # Param state
    z = param.Integer(default=0, bounds=(0, 0))        # bounds fixed in __init__
    window = param.Integer(default=0, bounds=(0, 0))   # bounds fixed in __init__
 
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.dataset = 'data' # location within the H5 file

        self.shape = self.get_volume_shape() # (z, y, x)

        self.param.z.bounds = (0, self.shape[0] - 1)
        self.param.window.bounds = (0, self.shape[0] // 2)
        self.z = 0
        self.window = 0

        self.z_controls = self._build_z_slider_controls()
        self.window_controls = self._build_max_projection_window_controls()


    def _get_volume_shape(self):
        """
        Get the shape of the 3D volume stored in the H5 file.
        Returns:
            tuple: Shape of the volume as (z, y, x).
        
        """
        with h5py.File(self.file_path, "r") as f:
            data = f[self.dataset]
            return data.shape  # (z, y, x)
        
    def _build_z_slider_controls(self) -> pn.Row:
        """ Create slider and buttons to select z slice.
        Returns:
            pn.Row: Panel row containing the z slice controls. Links to the class's 'z' param.
        """

        # Create slider
        self.z_slider = pn.widgets.IntSlider(
            name="Z slice (center)",
            start=self.param.z.bounds[0],
            end=self.param.z.bounds[1],
            value=self.z,
            width=300,
        )
        # Create increment buttons
        btn_minus = pn.widgets.Button(name="-", width=40)
        btn_plus = pn.widgets.Button(name="+", width=40)

        def dec_z(event):
            self.z = max(self.param.z.bounds[0], self.z - 1)

        def inc_z(event):
            self.z = min(self.param.z.bounds[1], self.z + 1)

        btn_minus.on_click(dec_z)
        btn_plus.on_click(inc_z)

        # Link slider <-> param
        self.z_slider.link(self, value="z")
        self.param.watch(lambda e: setattr(self.z_slider, "value", e.new), "z")

        z_controls = pn.Row(btn_minus, self.z_slider, btn_plus, align="center")
        return z_controls
    
    def _build_max_projection_window_controls(self) -> pn.Row:
        """ Create slider to select max projection half-window size. Links to the class's 'window' param.
        
        Returns:
            pn.Row: Panel row containing the max projection window controls. Links to the class's 'window' param.
        """

        # Create slider
        self.window_slider = pn.widgets.IntSlider(
            name="Max projection half-window (±z)",
            start=self.param.window.bounds[0],
            end=self.param.window.bounds[1],
            step=1,
            value=self.window,
            width=300,
        )

        # Link slider <-> param
        self.window_slider.link(self, value="window")
        self.param.watch(lambda e: setattr(self.window_slider, "value", e.new), "window")

        window_controls = pn.Row(self.window_slider, align="center")
        return window_controls
    

    def _load_slice_max(self, z: int, w: int) -> Image.Image:
        """
        Load max projection over z-w:z+w and return as PIL Image.
        """
        z_start = max(0, z - w)
        z_end = min(self.shape[0], z + w + 1)

        with h5py.File(self.file_path, "r") as f:
            dset = f[self.dataset]
            # shape: (z_window, y, x)
            vol = dset[z_start:z_end]
            # max projection along z
            arr = np.max(vol, axis=0)

        # Normalize to 0–255 uint8
        arr = arr.astype(np.float32)
        arr = arr - arr.min()
        if arr.max() > 0:
            arr = arr / arr.max()
        arr = (arr * 255).astype(np.uint8)

        return Image.fromarray(arr)
    
    @pn.depends("z", "window")
    def image_view(self):
        """ Render the current max-projected image as a Panel Image pane.
        """
        img = self._load_slice_max(self.z, self.window)
        return pn.pane.Image(
            img,
            sizing_mode="stretch_both",
            height=512,
        )

    def __panel__(self):
        # image_view is reactive due to @pn.depends on image_view
        return pn.Column(
            self.z_controls,
            self.window_controls,
            self.image_view,
        )