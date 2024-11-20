import io
import tempfile
import panel as pn
from io import BytesIO
from urllib.parse import urlparse
import param
from pathlib import Path
from panel.reactive import ReactiveHTML
import requests
import time
import os

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

KACHERY_ZONE = os.getenv("KACHERY_ZONE", "default")


class Fullscreen(ReactiveHTML):
    """A Fullscreen component that allows the user to toggle fullscreen mode.
    """
    
    object = param.Parameter()

    def __init__(self, object, **params):
        """Build fullscreen object
        """
        super().__init__(object=object, **params)

    _template = """
<div id="pn-container" class="pn-container">
        <span id="button" class="fullscreen-button" onclick="${script('maximize')}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 18 18">
        <path d="M4.5 11H3v4h4v-1.5H4.5V11zM3 7h1.5V4.5H7V3H3v4zm10.5 6.5H11V15h4v-4h-1.5v2.5zM11 3v1.5h2.5V7H15V3h-4z"></path>
                </svg>
        </span>
        <div id="object_el" class="object-container">${object}</div>
</div>
"""
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


class Media:
    """A Media object that can display images, videos, and other media types."""

    def __init__(self, reference, parent):
        """Build Media object"""

        self.parent = parent
        self.object = self.parse_reference(reference)

    def parse_reference(self, reference: str):
        """Parse the reference string and return the appropriate media object

        Parameters
        ----------
        reference : str
        """
        print(f"Parsing reference: {reference}")

        # Deal with swipe panels first
        if ";" in reference:
            return pn.layout.Swipe(
                self.parse_reference(reference.split(";")[0]),
                self.parse_reference(reference.split(";")[1]),
            )

        # Step 1: get the data
        # possible sources are: http, s3, local data asset, figurl
        if "http" in reference:
            reference_data = reference
        elif "s3" in reference:
            bucket = reference.split("/")[2]
            key = "/".join(reference.split("/")[3:])
            reference_data = _get_s3_data(self.parent.s3_client, bucket, key)
        elif "sha" in reference:
            reference_data = _get_kachery_cloud_url(reference)
        else:
            # assume local data asset_get_s3_asset
            reference_data = _get_s3_data(
                self.parent.s3_client,
                self.parent.s3_bucket,
                str(Path(self.parent.s3_prefix) / reference),
            )

        if not reference_data:
            return pn.pane.Alert(f"Failed to load asset: {reference}", alert_type="danger")

        # Step 2: parse the type and return the appropriate object
        return _parse_type(reference, reference_data)

    def panel(self):
        return Fullscreen(self.object, sizing_mode="stretch_both")


def _iframe_html(reference):
    return f'<iframe src="{reference}" style="height:100%; width:100%" frameborder="0"></iframe>'


def _parse_type(reference, data):
    """Interpret the media type from the reference string

    Parameters
    ----------
    reference : _type_
                    _description_
    data : _type_
                    _description_
    """
    if reference.endswith(".png") or reference.endswith(".jpg"):
        return pn.pane.Image(data, sizing_mode="scale_width", max_width=1200)
    elif reference.endswith(".mp4"):
        # Fetch the video data via GET request
        print(f"Fetching video from {reference}")
        response = requests.get(data)
        if response.status_code == 200:
            print("Video fetched successfully.")
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp_file.write(response.content)
            temp_file.close()
            print(temp_file.name)

            # Return the Video pane using the temporary file
            return pn.pane.Video(
                temp_file.name,  # Use the temporary file's path
                sizing_mode="scale_width",
                max_width=1200,
            )
        else:
            print(f"Failed to fetch video. Status code: {response.status_code}")
            return pn.pane.Alert(f"Failed to load video: {response.status_code}", alert_type="danger")
    elif "neuroglancer" in reference:
        iframe_html = f'<iframe src="{reference}" style="height:100%; width:100%" frameborder="0"></iframe>'
        return pn.pane.HTML(
            iframe_html, sizing_mode="stretch_both", height=1000
        )
    elif "http" in reference:
        return pn.widgets.StaticText(
            value=f'Reference: <a target="_blank" href="{reference}">link</a>'
        )
    else:
        return pn.widgets.StaticText(value=data)
    

def _get_s3_data(s3_client, bucket, key):
    """Get an S3 asset from the given bucket and key

    Parameters
    ----------
    s3_client : boto3.client
                    S3 client object
    bucket : str
                    S3 bucket name
    key : str
                    S3 key name
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = BytesIO(response["Body"].read())
        return data
    except Exception as e:
        return f"[ERROR] Failed to fetch asset {bucket}/{key}: {e}"


@pn.cache(ttl=3500)  # cache with slightly less than one hour timeout
def _get_kachery_cloud_url(hash: str):
    """Generate a kachery-cloud URL for the given hash

    Parameters
    ----------
    hash : str
        Generated from kcl.store_file()
    """
    timestamp = int(time.time() * 1000)

    print(f"Getting kachery-cloud URL for {hash}")

    # take the full hash, e.g. sha1://fb558dff5ed3c13751b6345af8a3128b25c4fa70?label=vid_side_camera_right_start_0_end_0.1.mp4 and just get the hash
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

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        return f"[ERROR] Failed to fetch asset {simplified_hash}: {response.text}"

    data = response.json()

    if not data["found"]:
        print (f"File not found in kachery-cloud: {simplified_hash}")
        return None
    else:
        return response.json()["url"]


def _get_s3_asset(s3_client, bucket, key):
    """Get an S3 asset from the given bucket and key

    Parameters
    ----------
    s3_client : boto3.client
                    S3 client object
    bucket : str
                    S3 bucket name
    key : str
                    S3 key name
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = BytesIO(response["Body"].read())
        return _parse_type(key, data)
    except Exception as e:
        return f"[ERROR] Failed to fetch asset {bucket}/{key}: {e}"
