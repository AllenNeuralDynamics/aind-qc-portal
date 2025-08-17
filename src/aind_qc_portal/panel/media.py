""" Media module for the AIND-QC Portal"""

import tempfile
import panel as pn
from io import BytesIO
import param
import boto3
import httpx
from pathlib import Path
import urllib.parse
import asyncio
from panel.custom import JSComponent
from tornado.ioloop import IOLoop
import requests
import time
import os
from .panel_utils import reference_is_image, reference_is_video, reference_is_pdf






class Media(param.Parameterized):
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

        self.spinner = pn.indicators.LoadingSpinner(value=True, size=50, name="Loading...")
        self.content = pn.Column(
            self.spinner,
        )

        IOLoop.current().add_callback(self.parse_reference)

    async def parse_reference(self, reference=None):
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
                    await self.parse_reference(reference.split(";")[0]),
                    await self.parse_reference(reference.split(";")[1]),
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
            self.reference_data = await _get_s3_file(self.reference_data, os.path.splitext(reference)[1])

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

        self.set_media_object(obj)

    def set_media_object(self, obj):
        """Set the media object to the given object"""
        self.spinner.visible = False
        self.content.clear()
        self.content.append(obj)

    def panel(self):  # pragma: no cover
        """Return the media object as a Panel object"""
        return Fullscreen(self.content, sizing_mode="stretch_width", max_height=1200)


# def _get_s3_file(url, ext):
#     """Get an S3 file from the given URL"""
#     try:
#         response = requests.get(url)
#         if response.status_code == 200:
#             with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
#                 temp_file.write(response.content)
#             return temp_file.name
#         else:
#             print(f"[ERROR] Failed to fetch asset {url}: {response.status_code} / {response.text}")
#             return None
#     except Exception as e:
#         print(f"[ERROR] Failed to fetch asset {url}, error: {e}")
#         return None




def encode_url(url):
    """Encode a URL"""
    base_url, query_string = url.split("?")
    encoded_query_string = urllib.parse.quote(query_string, safe="")

    return f"{base_url}?{encoded_query_string}"


@pn.cache(max_items=1000, policy="LFU")
def _get_s3_data(bucket, key):
    """Get an S3 asset from the given bucket and key

    Parameters
    ----------
    bucket : str
        S3 bucket name
    key : str
        S3 key name
    """

    # print((f"Getting S3 data for {bucket}/{key}"))
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = BytesIO(response["Body"].read())
        return data
    except Exception as e:
        return f"[ERROR] Failed to fetch asset {bucket}/{key}: {e}"


@pn.cache(max_items=1000, policy="LFU", ttl=3500)  # cache with slightly less than one hour timeout
async def _get_kachery_cloud_url(hash: str):
    """Generate a kachery-cloud URL for the given hash

    Parameters
    ----------
    hash : str
        Generated from kcl.store_file()
    """
    timestamp = int(time.time() * 1000)

    # print(f"Getting kachery-cloud URL for {hash}")

    # take the full hash string, e.g.
    # sha1://fb558dff5ed3c13751b6345af8a3128b25c4fa70?label=vid_side_camera_right_start_0_end_0.1.mp4
    # and just get the hash
    simplified_hash = hash.split("?")[0].split("://")[1]

    url = "https://kachery-gateway.figurl.org/api/gateway"
    headers = {
        "content-type": "application/json",
        "user-agent": "AIND-QC-PORTAL (Python; +qc.allenneuraldynamics.org)",
    }
    data = {
        "payload": {
            "type": "findFile",
            "timestamp": timestamp,
            "hashAlg": "sha1",
            "hash": simplified_hash,
            "zone": KACHERY_ZONE,
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)

    if response.status_code != 200:
        return f"[ERROR] Failed to fetch asset {simplified_hash}: {response.text}"

    data = response.json()

    if not data["found"]:
        print(f"File not found in kachery-cloud: {simplified_hash}")
        return None
    else:
        return response.json()["url"]
