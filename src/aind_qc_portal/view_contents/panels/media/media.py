"""Media class and associated helpers for the View app"""

import os
from pathlib import Path
from typing import Any, Optional

import panel as pn
import param
from panel.custom import PyComponent

from aind_qc_portal.view_contents.panels.media.utils import (
    Fullscreen,
    _get_s3_file,
    get_s3_url,
    parse_ephys_gui_app,
    _parse_rrd,
    _parse_sortingview,
    reference_is_image,
    reference_is_pdf,
    reference_is_video,
    clean_reference_prefix,
    clean_reference_url,
    is_presigned_url_valid,
)
from aind_qc_portal.view_contents.panels.media.z_slice_h5_viewer import ZSliceH5Viewer


class Media(PyComponent):
    """A Media object that can display images, videos, and other media types."""

    media_type = param.String(default="", doc="Type of object being displayed")

    def __init__(self, reference: str, s3_bucket: str, s3_prefix: str, raw_s3_loc: str):
        """Build a media object

        Parameters
        ----------
        reference : string
        parent : _type_
        """
        super().__init__()

        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.raw_s3_loc = raw_s3_loc

        self._init_panel_objects()
        self.parse_reference(reference)

    def _init_panel_objects(self):
        """Initialize empty panel objects"""
        self.content = pn.Column()

    def _get_media_data(self, reference: str):
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
            self.reference_data = _get_kachery_cloud_url(reference)
        elif reference.endswith(".h5") or reference.endswith(".hdf5"):
            # Handle H5 files - we'll construct the S3 path and open with fsspec later
            if "results/" in reference:
                reference = reference.split("results/")[1]
            reference_data = f"s3://{self.s3_bucket}/{str(Path(self.s3_prefix) / reference)}"
        else:
            # S3 asset in our bucket/key
            reference = clean_reference_prefix(reference)
            reference_data = get_s3_url(
                self.s3_bucket,
                str(Path(self.s3_prefix) / reference),
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

            if not reference_data:
                obj = pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger")

        if reference_is_image(reference):
            self.media_type = "Image"
            if not is_presigned_url_valid(reference_data):
                reference_data = get_s3_url(self.s3_bucket, str(Path(self.s3_prefix) / reference))
            obj = pn.pane.Image(reference_data, sizing_mode="scale_width", max_width=1200)
        elif reference_is_pdf(reference):
            self.media_type = "PDF"
            if not is_presigned_url_valid(reference_data):
                reference_data = get_s3_url(self.s3_bucket, str(Path(self.s3_prefix) / reference))
            obj = pn.pane.PDF(reference_data, sizing_mode="scale_width", max_width=1200, height=1000)
        elif reference_is_video(reference):
            self.media_type = "Video"
            if not is_presigned_url_valid(reference_data):
                reference_data = get_s3_url(self.s3_bucket, str(Path(self.s3_prefix) / reference))
            # Return the Video pane using the temporary file
            obj = pn.pane.Video(
                reference_data,
                sizing_mode="scale_width",
                max_width=1200,
            )
        elif reference.endswith(".h5") or reference.endswith(".hdf5"):
            # For H5 files, open with fsspec and create a ZSliceH5Viewer
            import fsspec
            print(f"Opening H5 file from S3: {self.reference_data}")

            fs = fsspec.filesystem("s3", anon=False)
            file_obj = fs.open(self.reference_data, "rb")
            # Extract filename from S3 path for display
            filename = self.reference_data.split("/")[-1]
            obj = ZSliceH5Viewer(file_obj, filename=filename)
        elif "rrd" in reference:
            # files should be in the format name_vX.Y.Z.rrd
            self.media_type = "Rerun"
            obj = _parse_rrd(reference, reference_data)
        elif "sortingview" in reference:
            self.media_type = "Sortingview"
            obj = _parse_sortingview(reference, reference_data, self)
        elif "neuroglancer" in reference:
            self.media_type = "Neuroglancer"
            iframe_html = f'<iframe src="{reference}" style="height:100%; width:100%" frameborder="0"></iframe>'
            obj = pn.pane.HTML(
                iframe_html,
                sizing_mode="stretch_width",
                height=1000,
            )
        elif "ephys.allenneuraldynamics.org" in reference:
            self.media_type = "Ephys GUI"
            obj = parse_ephys_gui_app(reference, reference_data, self.raw_s3_loc, f"{self.s3_bucket}/{self.s3_prefix}")
        elif "http" in reference:
            self.media_type = "Link"
            obj = pn.widgets.StaticText(value=f'Reference: <a target="_blank" href="{reference}">link</a>')
        else:
            self.media_type = "Text"
            obj = pn.widgets.StaticText(value=reference_data)

        return obj

    def parse_reference(self, reference: Optional[str] = None):
        """Parse the reference string and build the media object

        Parameters
        ----------
        data : str
        """
        if not reference:
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
            reference = reference.lstrip('/')

            reference_data = self._get_media_data(reference)
            if not reference_data:
                self.content.append(pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger"))
                return

            obj = self._get_media_object(reference, reference_data)

        self.content.append(obj)

    def __panel__(self):  # pragma: no cover
        """Return the media object as a Panel object"""
        return Fullscreen(self.content, sizing_mode="stretch_width", max_height=1200)
