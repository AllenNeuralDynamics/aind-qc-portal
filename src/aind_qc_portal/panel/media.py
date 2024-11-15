import panel as pn
from io import BytesIO
from urllib.parse import urlparse
import param
from pathlib import Path
from panel.reactive import ReactiveHTML

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
    color: white;
    transition-delay: 0.5s;
    transition: 0.5s;
    cursor: pointer;
    border-radius:4px;
}

.fullscreen-button:hover {
    transition: 0.5s;
    background-color: black;
}

.fullscreen-button:focus {
    background-color: black;
}
.pn-container, .object-container {
        height: 100%;
        width: 100%;
}
"""


class Fullscreen(ReactiveHTML):
    object = param.Parameter()

    def __init__(self, object, **params):
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

    def __init__(self, reference, parent):
        """Build Media object"""

        self.parent = parent
        self.object = self.parse_reference(reference)

    def parse_reference(self, reference):

        if ";" in reference:
            return pn.layout.Swipe(
                self.parse_reference(reference.split(";")[0]),
                self.parse_reference(reference.split(";")[1]),
            )
        if "http" in reference:
            parsed_url = urlparse(reference)

            if parsed_url.path.endswith(".png") or parsed_url.path.endswith(
                ".jpg"
            ):
                return pn.pane.Image(
                    reference, sizing_mode="scale_width", max_width=1200
                )
            elif parsed_url.path.endswith(".mp4"):
                return pn.pane.Video(
                    reference,
                    controls=True,
                    sizing_mode="scale_width",
                    max_width=1200,
                )
            elif parsed_url.path.endswith(".rrd"):
                src = f"https://app.rerun.io/version/0.9.0/index.html?url={reference}"
                return pn.pane.HTML(
                    _iframe_html(src), sizing_mode="stretch_both"
                )
            elif "neuroglancer" in reference:
                return pn.pane.HTML(
                    _iframe_html(reference), sizing_mode="stretch_both"
                )
            else:
                return pn.widgets.StaticText(
                    value=f'Reference: <a target="_blank" href="{reference}">link</a>'
                )
        elif "s3" in reference:
            bucket = reference.split("/")[2]
            key = "/".join(reference.split("/")[3:])
            return _get_s3_asset(self.parent.s3_client, bucket, key)

        elif "png" in reference:
            print(self.parent.s3_bucket)
            print(Path(self.parent.s3_prefix) / reference)
            return _get_s3_asset(
                self.parent.s3_client,
                self.parent.s3_bucket,
                str(Path(self.parent.s3_prefix) / reference),
            )

        elif reference == "ecephys-drift-map":
            return ""

        else:
            return f"Unable to parse {reference}"

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
        return pn.pane.Video(
            reference, controls=True, sizing_mode="scale_width", max_width=1200
        )
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
