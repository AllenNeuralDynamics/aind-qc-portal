""" Utility functions for the AIND QC Portal """

import re

import panel as pn
from aind_data_schema.core.quality_control import Status

from aind_qc_portal.layout import AIND_COLORS

VIEW_PREFIX = "/qc_app?id="
PROJECT_LINK_PREFIX = "/qc_project_app?project="


def raw_name_from_derived(derived_name: str) -> str:
    """Return the raw asset name from a derived asset name

    Derived assets have a pattern like:

    <subject_id>_<date>_<time>_<process>_<date>_<time>

    Some older assets have a pattern like:

    <platform>_<subject_id>_<date>_<time>_<process>_<date>_<time>

    Parameters
    ----------
    derived_name : str
        Name of a derived asset

    Returns
    -------
    str
        Name of the corresponding raw asset
    """

    if not derived_name:
        raise ValueError("Derived name cannot be empty")

    parts = derived_name.split("_")
    if len(parts) == 6:
        # Newer pattern without platform
        raw_name = "_".join(parts[0:3])
    elif len(parts) == 7:
        # Older pattern with platform
        raw_name = "_".join(parts[0:4])
    else:
        raise ValueError(f"Unexpected derived asset name format: {derived_name}")

    return raw_name


def get_user_name() -> str:
    """Return the user name from the current session"""
    if pn.state.user:
        return pn.state.user
    return "guest"


def format_link(link: str, text: str = "link"):
    """Format link as an HTML anchor tag

    Parameters
    ----------
    link : str
    text : str, optional
        by default "link"
    """
    return f'<a href="{link}" target="_blank">{text}</a>'


def format_css_background():
    """Add the custom CSS for the background to the panel configuration"""
    # Add the custom CSS
    background_color = AIND_COLORS[
        (
            pn.state.location.query_params["background"]
            if "background" in pn.state.location.query_params
            else "dark_blue"
        )
    ]
    BACKGROUND_CSS = f"""
    body {{
        background-color: {background_color} !important;
        background-image: url('/images/aind-pattern.svg') !important;
        background-size: 1200px;
    }}
    """
    pn.config.raw_css.append(BACKGROUND_CSS)  # type: ignore


def _qc_status_color(status: str):
    """Helper function to return the color for a given QC status

    Parameters
    ----------
    status : Status
        QC status

    Returns
    -------
    str
        Hex color code "#RRGGBB"
    """
    if status == "No QC":
        color = AIND_COLORS["yellow"]
    elif status == "Pass":
        color = AIND_COLORS["green"]
    elif status == "Fail":
        color = AIND_COLORS["red"]
    elif status == "Pending":
        color = AIND_COLORS["light_blue"]
    else:
        color = AIND_COLORS["grey"]
    return color


def qc_status_color(status: Status):
    """Return the color for a given QC status

    Parameters
    ----------
    status : Status
        QC status

    Returns
    -------
    str
        Hex color code "#RRGGBB"
    """
    return _qc_status_color(status.value)


def qc_status_color_css(status):
    """Return the CSS style string for a given QC status

    This function needs to take a string because it's used to style DataFrame columns

    Parameters
    ----------
    status : str
        QC status value

    Returns
    -------
    str
        CSS style string
    """
    return f"background-color: {_qc_status_color(status)}; color: white;"


def qc_status_html(status: Status | str, text: str = ""):
    """Return a formatted <span> tag with the color of the QC status

    Parameters
    ----------
    status : Status
        QC status
    text : str, optional
        Text to display, by default uses status.value

    Returns
    -------
    str
        HTML formatted string
    """
    if isinstance(status, Status):
        status = status.value

    return f'<span style="color:{_qc_status_color(status)};">{text if text else status}</span>'


def qc_status_link_html(status: str, link: str, text: str = ""):
    """Return a formatted <span> tag with the color of the QC status and a link"""
    return f'<span style="background-color:{_qc_status_color(status)};">{format_link(link, text)}</span>'


def replace_markdown_with_html(font_size: int = 12, inner_str: str = ""):
    """Replace markdown links with HTML anchor tags and set a font size"""
    # Find all links in the inner string
    link_pattern = re.compile(r"\[(.*?)\]\((.*?)\)")
    links = link_pattern.findall(inner_str)
    # Replace each link with an HTML anchor tag
    for link in links:
        inner_str = inner_str.replace(
            f"[{link[0]}]({link[1]})",
            f'<a href="{link[1]}" target="_blank">{link[0]}</a>',
        )
    # Apply the font size as a span element
    return f'<span style="font-size:{font_size}pt">{inner_str}</span>'


def df_scalar_to_list(data: dict):
    """Convert a dictionary of scalars to a dictionary of lists"""
    return {k: [v] if not isinstance(v, list) else v for k, v in data.items()}
