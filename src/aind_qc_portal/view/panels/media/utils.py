from panel.reactive import ReactiveHTML
import param


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
