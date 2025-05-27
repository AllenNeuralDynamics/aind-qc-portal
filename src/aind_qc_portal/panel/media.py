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
from panel.reactive import ReactiveHTML
from panel.custom import JSComponent
from tornado.ioloop import IOLoop
import requests
import time
import os
from .panel_utils import reference_is_image, reference_is_video, reference_is_pdf

s3_client = boto3.client(
    "s3",
    region_name="us-west-2",
    config=boto3.session.Config(signature_version="s3v4"),
)

MEDIA_TTL = 3600  # 1 hour
KACHERY_ZONE = os.getenv("KACHERY_ZONE", "aind")

CSS = """
:not(:root):fullscreen::backdrop {
        background: white;
}
.fullscreen-button {
    position: absolute;
    top: 0px;
    right: 0px;
    width: 24px;
    height: 24px;
    z-index: 10000;
    opacity: 1;
    color: gray;
    transition-delay: 0.5s;
    transition: 0.5s;
    cursor: pointer;
    border-radius:4px;
}

.fullscreen-button:hover {
    transition: 0.5s;
    color: white;
    background-color: black;
}

.fullscreen-button:focus {
    color: white;
    background-color: black;
}
.pn-container, .object-container {
        height: 100%;
        width: 100%;
}
"""


class CurationData(JSComponent):
    """A CurationData component that allows the user to toggle curation data."""

    curation_json = param.Dict()

    _esm = """
    export function render({ model }) {
        window.addEventListener('message', (event) => {
            // Check if the message is from the expected origin
            if (!event.origin.match(/^https?:\/\/(.*\.)?figurl\.org$/)) {
                console.warn('Received message from unexpected origin:', event.origin);
                return;
            }

            model.curation_json = event.data.curation;
            model.send_msg(model.curation_json);
        });
        return ""
    }
"""


class Fullscreen(ReactiveHTML):
    """A Fullscreen component that allows the user to toggle fullscreen mode."""

    object = param.Parameter()

    def __init__(self, object, **params):
        """Build fullscreen object"""
        super().__init__(object=object, **params)

    _path_str = "M4.5 11H3v4h4v-1.5H4.5V11zM3 7h1.5V4.5H7V3H3v4zm10.5 6.5H11V15h4v-4h-1.5v2.5zM11 3v1.5h2.5V7H15V3h-4z"
    _template = """
<div id="pn-container" class="pn-container">
        <span id="button" class="fullscreen-button" onclick="${script('maximize')}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 18 18">
                    <path d="{path_str}"></path>
                </svg>
        </span>
        <div id="object_el" class="object-container">${object}</div>
</div>
""".replace(
        "{path_str}", _path_str
    )
    _stylesheets = [CSS]
    _scripts = {
        "maximize": """
function isFullScreen() {
    return (
        document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.mozFullScreenElement ||
        document.msFullscreenElement
    )
}
function exitFullScreen() {
    if (document.exitFullscreen) {
        document.exitFullscreen()
    } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen()
    } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen()
    } else if (document.msExitFullscreen) {
        document.msExitFullscreen()
    }
}
function requestFullScreen(element) {
    if (element.requestFullscreen) {
        element.requestFullscreen()
    } else if (element.mozRequestFullScreen) {
        element.mozRequestFullScreen()
    } else if (element.webkitRequestFullscreen) {
        element.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT)
    } else if (element.msRequestFullscreen) {
        element.msRequestFullscreen()
    }
}

function toggleFullScreen() {
    if (isFullScreen()) {
        exitFullScreen()
    } else {
        requestFullScreen(button.parentElement)
    }
}
toggleFullScreen()
"""
    }


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

        await asyncio.sleep(5)

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


async def _get_s3_file(url, ext):
    """Get an S3 file from the given URL asynchronously"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(response.content)
            return temp_file.name
        else:
            print(f"[ERROR] Failed to fetch asset {url}: {response.status_code} / {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Failed to fetch asset {url}, error: {e}")
        return None


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


def _parse_rrd(reference, data):
    """Parse an RRD file and return the appropriate object"""
    if "_v" in reference:
        full_version = reference.split("_v")[1].split(".rrd")[0]
    else:
        full_version = "0.19.1"
    src = f"https://app.rerun.io/version/{full_version}/index.html?url={encode_url(data)}"
    iframe_html = f'<iframe src="{src}" style="height:100%; width:100%" frameborder="0"></iframe>'
    return pn.pane.HTML(
        iframe_html,
        sizing_mode="stretch_width",
        height=1000,
    )


def _parse_sortingview(reference, data, media_obj):
    """Parse a sortingview URL and return the appropriate object"""
    iframe_html = f'<iframe src="{data}" style="height:100%; width:100%" frameborder="0"></iframe>'
    curation_data = CurationData()

    def on_msg(event):
        """Handle messages from the sortingview iframe"""
        print(f"Received message: {event.data}")
        if not media_obj.value_callback:
            raise ValueError("No value callback set for sortingview object")

        media_obj.value_callback(event.data)
        media_obj.parent.set_submit_dirty()

    curation_data.on_msg(on_msg)
    return pn.Column(
        pn.pane.HTML(
            iframe_html,
            sizing_mode="stretch_width",
            height=1000,
        ),
        curation_data,
    )


def encode_url(url):
    """Encode a URL"""
    base_url, query_string = url.split("?")
    encoded_query_string = urllib.parse.quote(query_string, safe="")

    return f"{base_url}?{encoded_query_string}"


@pn.cache(max_items=10000, policy="LFU", ttl=MEDIA_TTL)
def _get_s3_url(bucket, key):
    """Get a presigned URL to an S3 asset

    Parameters
    ----------
    bucket : str
        S3 bucket name
    key : str
        S3 key name
    """
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=MEDIA_TTL,
    )


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
