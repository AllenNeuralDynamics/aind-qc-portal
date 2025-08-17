"""Media class and associated helpers for the View app"""

from panel.custom import PyComponent
import panel as pn
import param
from aind_qc_portal.view.panels.media.utils import reference_is_image, reference_is_pdf, reference_is_video, Fullscreen, _get_s3_file


class Media(PyComponent):
    """A Media object that can display images, videos, and other media types."""

    reference = param.String(default="")
    reference_data = param.String(default=None, allow_None=True)

    def __init__(self, reference: str, parent, callback=None):
        """Build a media object

        Parameters
        ----------
        reference : string
        parent : _type_
        callback : _type_, optional
        """

        self.parent = parent
        self.reference = reference
        self.value_callback = callback
        
        self.content = pn.Column()
        self.parse_reference(reference)

    def parse_reference(self, reference=None):
        """Parse the reference string and return the appropriate media object

        Parameters
        ----------
        reference : str
        """
        if not reference:
            reference = self.reference
        print(f"Parsing reference: {self.reference}")

        # Deal with swipe panels first
        if ";" in reference:
            self.set_media_object(
                pn.layout.Swipe(
                    self.parse_reference(reference.split(";")[0]),
                    self.parse_reference(reference.split(";")[1]),
                )
            )
            return

        # Strip slashes at the start of the reference
        if reference.startswith("/"):
            reference = reference[1:]

        # Step 1: get the data
        # possible sources are: http, s3, local data asset, figurl
        if "http" in reference:
            self.reference_data = reference
        elif "s3" in reference:
            bucket = reference.split("/")[2]
            key = "/".join(reference.split("/")[3:])
            self.reference_data = _get_s3_url(bucket, key)
        elif "sha" in reference:
            self.reference_data = _get_kachery_cloud_url(reference)
        else:
            # assume local data asset_get_s3_asset

            # if a user appends extra things up to results/, strip that
            if "results/" in reference:
                reference = reference.split("results/")[1]
            self.reference_data = _get_s3_url(
                self.parent.s3_bucket,
                str(Path(self.parent.s3_prefix) / reference),
            )

        if not self.reference_data:
            self.set_media_object(pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger"))
            return

        # print(f"Parsing type: {reference} with data: {data}")

        if self.reference_data and "https://s3" in self.reference_data:
            self.reference_data = _get_s3_file(self.reference_data, os.path.splitext(reference)[1])

            if not self.reference_data:
                obj = pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger")

        if reference_is_image(reference):
            obj = pn.pane.Image(self.reference_data, sizing_mode="scale_width", max_width=1200)
        elif reference_is_pdf(reference):
            obj = pn.pane.PDF(self.reference_data, sizing_mode="scale_width", max_width=1200, height=1000)
        elif reference_is_video(reference):
            # Return the Video pane using the temporary file
            obj = pn.pane.Video(
                self.reference_data,
                sizing_mode="scale_width",
                max_width=1200,
            )
        elif "rrd" in reference:
            # files should be in the format name_vX.Y.Z.rrd
            obj = _parse_rrd(reference, self.reference_data)
        elif "sortingview" in reference:
            obj = _parse_sortingview(reference, self.reference_data, self)
        elif "neuroglancer" in reference:
            iframe_html = f'<iframe src="{reference}" style="height:100%; width:100%" frameborder="0"></iframe>'
            obj = pn.pane.HTML(
                iframe_html,
                sizing_mode="stretch_width",
                height=1000,
            )
        elif "http" in reference:
            obj = pn.widgets.StaticText(value=f'Reference: <a target="_blank" href="{reference}">link</a>')
        else:
            obj = pn.widgets.StaticText(value=self.reference_data)

        self.content.append(obj)

    def __panel__(self):  # pragma: no cover
        """Return the media object as a Panel object"""
        return Fullscreen(self.content, sizing_mode="stretch_width", max_height=1200)
