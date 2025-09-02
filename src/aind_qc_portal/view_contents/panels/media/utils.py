import os
import tempfile

import boto3
import httpx
import panel as pn
import param
from panel.custom import JSComponent
from panel.reactive import ReactiveHTML

s3_client = boto3.client(
    "s3",
    region_name="us-west-2",
    config=boto3.session.Config(signature_version="s3v4"),
)

MEDIA_TTL = 3600  # 1 hour
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
""".replace(
        "{path_str}", _path_str
    )
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
        or reference.endswith(".jpg")  # noqa: W503
        or reference.endswith(".gif")  # noqa: W503
        or reference.endswith(".jpeg")  # noqa: W503
        or reference.endswith(".svg")  # noqa: W503
        or reference.endswith(".tiff")  # noqa: W503
        or reference.endswith(".webp")  # noqa: W503
    )


def reference_is_video(reference):
    """Check if the reference is a video"""
    return reference.endswith(".mp4") or reference.endswith(".avi") or reference.endswith(".webm")


def reference_is_pdf(reference):
    """Check if the reference is a pdf"""
    return reference.endswith(".pdf")


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
