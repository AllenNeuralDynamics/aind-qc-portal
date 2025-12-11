from pathlib import Path

import h5py
import numpy as np
import panel as pn
import param
from panel.custom import PyComponent
from PIL import Image


class ZSliceH5Viewer(PyComponent):
    """Panel component to visualize z-slices of 3d data stored in an H5 file with max projection.

    Args:
        file_path_or_object: Either a string path to the H5 file or a file-like object (e.g., from fsspec).
        filename (str, optional): Display name for the file. If not provided, will try to extract from
            file_path_or_object.

    Attributes:
        z (int): Current z slice index (center of max projection).
        window (int): Half-window size for max projection.
    """

    # Param state
    z = param.Integer(default=0, bounds=(0, 0))  # bounds fixed in __init__
    window = param.Integer(default=0, bounds=(0, 0))  # bounds fixed in __init__
    contrast = param.Range(default=(0, 99), bounds=(0, 100), step=1)

    def __init__(self, file_path_or_object, filename=None):
        super().__init__()

        self.file_obj = file_path_or_object
        self.dataset = "data"  # location within the H5 file

        # Open H5 file once and keep it open
        self._h5file = h5py.File(self.file_obj, "r")
        self._h5dset = self._h5file[self.dataset]

        # Determine filename for display
        if filename:
            self.filename = filename
        elif isinstance(file_path_or_object, str):
            self.filename = Path(file_path_or_object).name
        else:
            self.filename = "H5 Data"

        self.shape = self._h5dset.shape  # (z, y, x)

        self.param.z.bounds = (0, self.shape[0] - 1)
        self.param.window.bounds = (0, self.shape[0] // 2)
        self.z = 0
        self.window = 0

        self.image = pn.pane.Image(sizing_mode="stretch_both")

        self.z_controls = self._build_z_slider_controls()
        self.window_controls = self._build_max_projection_window_controls()
        self.contrast_controls = self._build_contrast_controls()

        self.param.watch(self.image_view, ["z", "window", "contrast"])
        self.image_view()

    def __del__(self):
        """Close the H5 file when the object is destroyed."""
        if hasattr(self, "_h5file") and self._h5file:
            self._h5file.close()

    def _build_z_slider_controls(self) -> pn.Row:
        """Create slider and buttons to select z slice.
        Returns:
            pn.Row: Panel row containing the z slice controls. Links to the class's 'z' param.
        """

        # Create slider linked to z param
        self.z_slider = pn.widgets.IntSlider.from_param(self.param.z, width=300, name="Z Slice")

        # Create increment buttons
        btn_minus = pn.widgets.Button(name="-", width=40)
        btn_plus = pn.widgets.Button(name="+", width=40)

        def dec_z(event):
            self.z = max(self.param.z.bounds[0], self.z - 1)

        def inc_z(event):
            self.z = min(self.param.z.bounds[1], self.z + 1)

        btn_minus.on_click(dec_z)
        btn_plus.on_click(inc_z)

        z_controls = pn.Row(btn_minus, self.z_slider, btn_plus, align="center")
        return z_controls

    def _build_max_projection_window_controls(self) -> pn.Row:
        """Create slider to select max projection half-window size. Links to the class's 'window' param.

        Returns:
            pn.Row: Panel row containing the max projection window controls. Links to the class's 'window' param.
        """

        # Create slider linked to window param
        self.window_slider = pn.widgets.IntSlider.from_param(
            self.param.window, width=300, name="Max projection half-window (z±window)"
        )

        window_controls = pn.Row(self.window_slider, align="center")
        return window_controls

    def _build_contrast_controls(self) -> pn.Row:
        """Create slider for contrast percentile (0-100).
        Returns:
            pn.Row: Panel row containing upper percentile for contrast normalization
        """
        self.contrast_slider = pn.widgets.RangeSlider.from_param(
            self.param.contrast,
            width=300,
            name="Percentile contrast",
        )
        return pn.Row(self.contrast_slider, align="center")

    @pn.cache()
    def _get_cached_slice(self, z: int, w: int):
        """
        Load and cache max projection data over z-w:z+w.
        Uses pn.cache() to avoid recomputing identical slices.

        Args:
            z (int): Center z-slice index for the max projection.
            w (int): Half-window size; number of slices to include on each side of z.

        Returns:
            np.ndarray: Raw max projection array (float32).
        """
        z_start = max(0, z - w)
        z_end = min(self.shape[0], z + w + 1)

        # Read from already-open H5 dataset
        vol = self._h5dset[z_start:z_end]
        # Max projection along z
        arr = np.max(vol, axis=0).astype(np.float32)
        return arr

    def _load_slice_max(self, z: int, w: int) -> Image.Image:
        """
        Load max projection over z-w:z+w and return as a normalized PIL Image.

        Args:
            z (int): Center z-slice index for the max projection.
            w (int): Half-window size; number of slices to include on each side of z.

        Returns:
            PIL.Image.Image: Image containing the normalized max projection over the specified z window.
        """
        # Get cached slice data
        arr = self._get_cached_slice(z, w)

        low_p, high_p = self.contrast  # in [0, 100]

        if low_p <= 0 and high_p >= 100:
            # Full dynamic range
            low_val, high_val = arr.min(), arr.max()
        elif low_p <= 0:
            low_val = arr.min()
            high_val = np.percentile(arr, high_p)
        elif high_p >= 100:
            low_val = np.percentile(arr, low_p)
            high_val = arr.max()
        else:
            # Both are percentiles
            low_val, high_val = np.percentile(arr, [low_p, high_p])

        if high_val <= low_val:
            high_val = low_val + 1e-6

        arr = np.clip(arr, low_val, high_val)
        arr = (arr - low_val) / (high_val - low_val)
        arr = (arr * 255).astype(np.uint8)

        return Image.fromarray(arr)

    def image_view(self, event=None):
        """Render the current max-projected image as a Panel Image pane."""
        self.image.loading = True
        try:
            img = self._load_slice_max(self.z, self.window)
            self.image.object = img
        finally:
            self.image.loading = False

    def __panel__(self):

        filename_text_wiget = pn.widgets.StaticText(name="File Name", value=self.filename, align="center")

        return pn.Column(
            filename_text_wiget,
            self.z_controls,
            self.window_controls,
            self.contrast_controls,
            self.image,
            min_height=600,
        )
