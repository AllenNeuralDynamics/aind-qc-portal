"""Media class and associated helpers for the View app"""

import os
from pathlib import Path
from typing import Any, Optional

import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view_contents.panels.media.curation_apps.z_slice_h5_viewer import ZSliceH5Viewer
from aind_qc_portal.view_contents.panels.media.utils import (
    Fullscreen,
    _get_s3_file,
    _parse_rrd,
    _parse_sortingview,
    clean_reference_prefix,
    clean_reference_url,
    get_s3_url,
    is_presigned_url_valid,
    parse_ephys_gui_app,
    reference_is_image,
    reference_is_pdf,
    reference_is_video,
)


class Media(PyComponent):
    """A Media object that can display images, videos, and other media types."""

    media_type = param.String(default="", doc="Type of object being displayed")
    loaded = param.Boolean(default=False, doc="Whether the media has been loaded")
    refresh_trigger = param.Integer(default=0, doc="Counter to trigger URL refresh")

    def __init__(
        self,
        reference: str,
        s3_bucket: str,
        s3_prefix: str,
        raw_s3_loc: str,
        lazy_load: bool = True,
        value_callback=None,
        parent=None,
    ):
        """Build a media object

        Parameters
        ----------
        reference : string
        s3_bucket : str
        s3_prefix : str
        raw_s3_loc : str
        lazy_load : bool
            If True, display a button that loads media when clicked. If False, load immediately.
        value_callback : callable, optional
            Callback function to handle value updates from interactive media (e.g., sortingview, ephys GUI)
        parent : object, optional
            Parent object that has a set_submit_dirty method for marking changes
        """
        super().__init__()

        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.raw_s3_loc = raw_s3_loc
        self.reference = reference
        self.lazy_load = lazy_load
        self.value_callback = value_callback
        self.parent = parent
        self._refresh_callback = None
        self._current_reference_data = None

        self._init_panel_objects()

        if not lazy_load:
            self._load_media()
        else:
            # Parse reference to determine media type without loading
            self._determine_media_type(reference)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.content = pn.Column()
        self.image_pane = pn.pane.Image(sizing_mode="scale_width", max_width=1200)
        self.pdf_pane = pn.pane.PDF(sizing_mode="scale_width", max_width=1200, height=1000)
        self.video_pane = pn.pane.Video(sizing_mode="scale_width", max_width=1200)

    def _determine_media_type(self, reference: str):
        """Determine the media type from the reference without loading the full media object"""
        if not reference or not isinstance(reference, str):
            print(f"Could not determine media type for reference: {reference} of type {type(reference)}")
            self.media_type = "Unknown"
            return

        if reference_is_image(reference):
            self.media_type = "Image"
        elif reference_is_pdf(reference):
            self.media_type = "PDF"
        elif reference_is_video(reference):
            self.media_type = "Video"
        elif "rrd" in reference:
            self.media_type = "Rerun"
        elif "sortingview" in reference:
            self.media_type = "Sortingview"
        elif "neuroglancer" in reference:
            self.media_type = "Neuroglancer"
        elif "ephys.allenneuraldynamics.org" in reference:
            self.media_type = "Ephys GUI"
        elif "http" in reference:
            self.media_type = "Link"
        else:
            self.media_type = "Text"

    def load(self):
        """Public method to trigger media loading"""
        if not self.loaded:
            self._load_media()

    def _load_media(self):
        """Load and display the actual media content"""
        self.loaded = True
        self.content.clear()
        self.content.loading = True
        self.parse_reference(self.reference)
        self.content.loading = False
        self._start_refresh_callback()

    def _get_media_data(self, reference: str, force_refresh: bool = False):
        """Parse a reference string and convert to a data object"""
        if "http" in reference:
            # Any HTTP URL
            reference_data = clean_reference_url(reference)
        elif "s3" in reference:
            # S3 asset that is *not* in our bucket/key
            bucket = reference.split("/")[2]
            key = "/".join(reference.split("/")[3:])
            reference_data = get_s3_url(bucket, key)
        elif "sha" in reference:
            raise ValueError("Kachery cloud references are no longer supported")
        elif reference.endswith(".h5") or reference.endswith(".hdf5"):
            # Handle H5 files - we'll construct the S3 path and open with fsspec later
            if "results/" in reference:
                reference = reference.split("results/")[1]
            reference_data = f"s3://{self.s3_bucket}/{str(Path(self.s3_prefix) / reference)}"
        else:
            # S3 asset in our bucket/key
            reference_data = get_s3_url(
                self.s3_bucket,
                str(Path(self.s3_prefix) / clean_reference_prefix(reference)),
            )

        return reference_data

    def _get_media_object(self, reference: str, reference_data: Any):
        """Parse the reference string and return the appropriate media object

        Parameters
        ----------
        reference : str
        reference_data: Any
        """

        if reference_data and "https://s3" in reference_data:
            reference_data = _get_s3_file(reference_data, os.path.splitext(reference)[1])

        handlers = [
            (reference_is_image(reference), self._handle_image),
            (reference_is_pdf(reference), self._handle_pdf),
            (reference_is_video(reference), self._handle_video),
            (reference.endswith((".h5", ".hdf5")), self._handle_h5),
            ("rrd" in reference, self._handle_rerun),
            ("sortingview" in reference, self._handle_sortingview),
            ("neuroglancer" in reference, self._handle_neuroglancer),
            ("ephys.allenneuraldynamics.org" in reference, self._handle_ephys_gui),
            ("http" in reference, self._handle_link),
        ]

        for condition, handler in handlers:
            if condition:
                return handler(reference, reference_data)

        return self._handle_text(reference, reference_data)

    def _handle_image(self, reference: str, reference_data: Any):
        """Handle image media type"""
        self.media_type = "Image"
        if not is_presigned_url_valid(reference_data):
            reference_data = get_s3_url(self.s3_bucket, str(Path(self.s3_prefix) / clean_reference_prefix(reference)))
        self._current_reference_data = reference_data
        self.image_pane.object = reference_data
        return self.image_pane

    def _handle_pdf(self, reference: str, reference_data: Any):
        """Handle PDF media type"""
        self.media_type = "PDF"
        if not is_presigned_url_valid(reference_data):
            reference_data = get_s3_url(self.s3_bucket, str(Path(self.s3_prefix) / clean_reference_prefix(reference)))
        self._current_reference_data = reference_data
        self.pdf_pane.object = reference_data
        return self.pdf_pane

    def _handle_video(self, reference: str, reference_data: Any):
        """Handle video media type"""
        self.media_type = "Video"
        if not is_presigned_url_valid(reference_data):
            reference_data = get_s3_url(self.s3_bucket, str(Path(self.s3_prefix) / clean_reference_prefix(reference)))
        self._current_reference_data = reference_data
        self.video_pane.object = reference_data
        return self.video_pane

    def _handle_h5(self, reference: str, reference_data: Any):
        """Handle H5/HDF5 files"""
        import fsspec

        print(f"Opening H5 file from S3: {reference_data}")
        fs = fsspec.filesystem("s3", anon=False)
        file_obj = fs.open(reference_data, "rb")
        filename = reference_data.split("/")[-1]
        return ZSliceH5Viewer(file_obj, filename=filename)

    def _handle_rerun(self, reference: str, reference_data: Any):
        """Handle Rerun media type"""
        self.media_type = "Rerun"
        return _parse_rrd(reference, reference_data)

    def _handle_sortingview(self, reference: str, reference_data: Any):
        """Handle Sortingview media type"""
        self.media_type = "Sortingview"
        return _parse_sortingview(reference, reference_data, self)

    def _handle_neuroglancer(self, reference: str, reference_data: Any):
        """Handle Neuroglancer media type"""
        self.media_type = "Neuroglancer"
        iframe_html = f'<iframe src="{reference}" style="height:100%; width:100%" frameborder="0"></iframe>'
        return pn.pane.HTML(iframe_html, sizing_mode="stretch_width", height=1000)

    def _handle_ephys_gui(self, reference: str, reference_data: Any):
        """Handle Ephys GUI media type"""
        self.media_type = "Ephys GUI"
        return parse_ephys_gui_app(
            reference, reference_data, self.raw_s3_loc, f"{self.s3_bucket}/{self.s3_prefix}", self
        )

    def _handle_link(self, reference: str, reference_data: Any):
        """Handle HTTP link media type"""
        self.media_type = "Link"
        return pn.widgets.StaticText(value=f'Reference: <a target="_blank" href="{reference}">link</a>')

    def _handle_text(self, reference: str, reference_data: Any):
        """Handle text media type (default fallback)"""
        self.media_type = "Text"
        return pn.widgets.StaticText(value=reference_data)

    def parse_reference(self, reference: Optional[str] = None):
        """Parse the reference string and build the media object

        Parameters
        ----------
        data : str
        """
        if not reference or not isinstance(reference, str):
            return

        print(f"Parsing reference: {reference}")

        if ";" in reference:
            # Deal with swipe panels, split the reference and build two media objects
            reference_left = reference.split(";")[0]
            reference_right = reference.split(";")[1]
            obj = pn.layout.Swipe(
                self._get_media_object(reference_left, self._get_media_data(reference_left)),
                self._get_media_object(reference_right, self._get_media_data(reference_right)),
            )
        else:
            # Single-media references
            reference = reference.lstrip("/")

            reference_data = self._get_media_data(reference)
            if not reference_data:
                self.content.append(pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger"))
                return

            obj = self._get_media_object(reference, reference_data)

        if not obj:
            obj = pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger")

        self.content.append(obj)

    def _start_refresh_callback(self):
        """Start periodic callback to refresh URLs before they expire"""
        if self.media_type not in ["Image", "PDF", "Video"]:
            return

        if self._refresh_callback:
            self._refresh_callback.stop()

        refresh_interval = 50 * 60 * 1000
        self._refresh_callback = pn.state.add_periodic_callback(self._refresh_url, period=refresh_interval)

    def _refresh_url(self):
        """Refresh the presigned URL for the current media"""
        if not self.reference or not self._current_reference_data:
            return

        print(f"Refreshing URL for {self.reference}")

        reference_data = self._get_media_data(self.reference, force_refresh=True)
        self._current_reference_data = reference_data

        if self.media_type == "Image":
            self.image_pane.object = reference_data
        elif self.media_type == "PDF":
            self.pdf_pane.object = reference_data
        elif self.media_type == "Video":
            self.video_pane.object = reference_data

        self.refresh_trigger += 1

    def _send_message_to_iframe(self, message: dict):
        """Send a postMessage to the iframe

        Parameters
        ----------
        message : dict
            Message object to send to the iframe
        """
        import json

        message_json = json.dumps(message)
        script = f"""
        <script>
        (function() {{
            const iframes = document.querySelectorAll('iframe');
            const message = {message_json};
            iframes.forEach(iframe => {{
                iframe.contentWindow.postMessage(message, '*');
            }});
        }})();
        </script>
        """

        # Add the script to the content to execute the postMessage
        if hasattr(self, "content") and self.content:
            script_pane = pn.pane.HTML(script)
            if script_pane not in self.content:
                self.content.append(script_pane)

    @param.depends("loaded", watch=False)
    def __panel__(self):  # pragma: no cover
        """Return the media object as a Panel object"""
        if self.lazy_load and not self.loaded:
            return pn.Column(pn.pane.Markdown("*Loading...*"), sizing_mode="stretch_width")
        return Fullscreen(self.content, sizing_mode="stretch_width", max_height=1200)
