"""Util functions"""

import os
import tempfile
import urllib
from urllib.parse import quote, unquote

import boto3
import httpx
import panel as pn
import param
import requests
from panel.custom import JSComponent
from panel.reactive import ReactiveHTML


def get_s3_client(reference=None):
    """Get a fresh boto3 S3 client with current credentials

    Parameters
    ----------
    reference : str, optional
        Reference string (bucket name or URL) to determine which client to use.
        If contains 'codeocean', returns a client with assumed role credentials.
        Otherwise returns a standard S3 client.

    Returns
    -------
    boto3.client
        Fresh S3 client with current credentials
    """
    use_codeocean = reference and "codeocean" in reference

    if os.getenv("BYPASS_CODEOCEAN_S3", "0") == "1":
        return boto3.client(
            "s3",
            region_name="us-west-2",
            config=boto3.session.Config(signature_version="s3v4"),
        )

    if use_codeocean:
        sts_client = boto3.client("sts")
        response = sts_client.assume_role(
            RoleArn="arn:aws:iam::467914378000:role/AindCodeOceanBucketCrossAccountAccess",
            RoleSessionName="qc-portal-session",
        )
        creds = response["Credentials"]

        role_session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
        return role_session.client(
            "s3",
            region_name="us-west-2",
            config=boto3.session.Config(signature_version="s3v4"),
        )
    else:
        return boto3.client(
            "s3",
            region_name="us-west-2",
            config=boto3.session.Config(signature_version="s3v4"),
        )


MEDIA_TTL = 60 * 60  # 1 hour
KACHERY_ZONE = os.getenv("KACHERY_ZONE", "aind")
FULLSCREEN_CSS = """
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
""".replace("{path_str}", _path_str)
    _stylesheets = [FULLSCREEN_CSS]
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


def reference_is_image(reference):
    """Check if the reference is an image"""
    return (
        reference.endswith(".png")
        or reference.endswith(".jpg")
        or reference.endswith(".gif")
        or reference.endswith(".jpeg")
        or reference.endswith(".svg")
        or reference.endswith(".tiff")
        or reference.endswith(".webp")
    )


def reference_is_video(reference):
    """Check if the reference is a video"""
    return reference.endswith(".mp4") or reference.endswith(".avi") or reference.endswith(".webm")


def reference_is_pdf(reference):
    """Check if the reference is a pdf"""
    return reference.endswith(".pdf")


def clean_reference_prefix(reference: str):
    """Remove results/ prefix from reference"""
    if "results/" in reference:
        reference = reference.split("results/")[1]

    return reference


def clean_reference_url(reference: str):
    """Make sure a URL isn't encoded"""
    if "http" in reference:
        reference = unquote(reference)
    return reference


def is_presigned_url_valid(url: str) -> bool:
    """Check if a presigned S3 URL is valid"""
    try:
        # Use GET with Range header to fetch only 1 byte instead of HEAD
        # S3 presigned URLs with SignedHeaders=host fail with HEAD due to extra headers
        headers = {"Range": "bytes=0-0"}
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=5)

        # Valid URLs return 200 OK, 206 Partial Content, or 416 Range Not Satisfiable
        if response.status_code in (200, 206, 416):
            return True

        # Expired or invalid URLs from S3 return 403 Forbidden
        # with specific S3 error codes in headers or body
        if response.status_code == 403:
            return False

        # Other codes may indicate permissions or other problems
        return False

    except requests.RequestException:
        return False


def get_s3_url(bucket, key):
    """Get a presigned URL to an S3 asset

    Parameters
    ----------
    bucket : str
        S3 bucket name
    key : str
        S3 key name
    """
    if not bucket or not key:
        return None

    client = get_s3_client(bucket)
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=MEDIA_TTL,
    )
    return url


def _get_s3_file(url, ext):
    """Get an S3 file from the given URL synchronously"""
    try:
        with httpx.Client() as client:
            response = client.get(url)

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


def encode_url(url):
    """Encode a URL"""
    base_url, query_string = url.split("?")
    encoded_query_string = urllib.parse.quote(query_string, safe="")

    return f"{base_url}?{encoded_query_string}"


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


def parse_ephys_gui_app(reference, data, raw_asset_s3, derived_asset_s3, media_obj):
    """Parse an ephys GUI URL and return the appropriate object with callback support"""
    data = data.replace("{derived_asset_location}", f"s3://{derived_asset_s3.lstrip('s3://')}")
    data = data.replace("{raw_asset_location}", f"s3://{raw_asset_s3.lstrip('s3://')}")
    data = quote(data, safe=":/?&=")
    iframe_html = f'<iframe src="{data}" style="height:100%; width:100%" frameborder="0"></iframe>'

    if media_obj.value_callback and media_obj.parent:
        curation_data = EphysGUICurationData()

        def on_msg(event):
            """Handle messages from the ephys GUI iframe"""
            print(f"Received message from Ephys GUI: {event.data}")
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
    else:
        return pn.Column(
            pn.pane.HTML(
                iframe_html,
                sizing_mode="stretch_width",
                height=1000,
            ),
        )


class CurationData(JSComponent):
    """A CurationData component that allows the user to toggle curation data."""

    curation_json = param.Dict()

    _esm = r"""
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


class EphysGUICurationData(JSComponent):
    """A CurationData component for Ephys GUI that receives curation data from iframe messages."""

    curation_json = param.Dict()

    _esm = r"""
    export function render({ model }) {
        window.addEventListener('message', (event) => {
            // Check if the message is from the expected origin (ephys GUI domain)
            if (!event.origin.match(/^https?:\/\/(.*\.)?allenneuraldynamics\.org$/)) {
                console.warn('Received message from unexpected origin:', event.origin);
                return;
            }

            model.curation_json = event.data;
            model.send_msg(model.curation_json);
        });
        return ""
    }
"""
