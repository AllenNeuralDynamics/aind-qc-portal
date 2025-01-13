from datetime import timedelta
import re

import numpy as np
import panel as pn
from aind_data_schema.core.quality_control import Status

ASSET_LINK_PREFIX = "/qc_asset_app?id="
QC_LINK_PREFIX = "/qc_app?id="
PROJECT_LINK_PREFIX = "/qc_project_app?project="

AIND_COLORS = colors = {
    "dark_blue": "#003057",
    "light_blue": "#2A7DE1",
    "green": "#1D8649",
    "yellow": "#FFB71B",
    "grey": "#7C7C7F",
    "red": "#FF5733",
}

OUTER_STYLE = {
    "background": "#ffffff",
    "border-radius": "5px",
    "border": "2px solid black",
    "padding": "10px",
    "box-shadow": "5px 5px 5px #bcbcbc",
    "margin": "5px",
}


# Define minimum ranges based on your criteria
ONE_WEEK = timedelta(weeks=1)
ONE_MONTH = timedelta(days=30)
THREE_MONTHS = timedelta(days=90)
ONE_YEAR = timedelta(days=365)
TWO_YEARS = timedelta(days=730)
FIVE_YEARS = timedelta(days=1825)


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
    return f"background-color: {_qc_status_color(status)}"


def qc_status_html(status: Status, text: str = ""):
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
    return f'<span style="color:{qc_status_color(status)};">{text if text else status.value}</span>'


def range_unit_format(time_range):
    """Compute the altair plot axis unit and format for displaying a time range

    """
    if time_range < ONE_WEEK:
        unit = "day"
        format = "%b %d"
    elif time_range < ONE_MONTH:
        unit = "week"
        format = "%b %d"
    elif time_range < THREE_MONTHS:
        unit = "week"
        format = "%b %d"
    elif time_range < ONE_YEAR:
        unit = "month"
        format = "%b"
    elif time_range < TWO_YEARS:
        unit = "year"
        format = "%b"
    elif time_range < FIVE_YEARS:
        unit = "year"
        format = "%Y"
    else:
        raise ValueError("Time range is too large")

    return unit, format


def timestamp_range(min_date, max_date):
    """Compute the min/max range of a set of timestamps

    Parameters
    ----------
    min : datetime.timestamp
        _description_
    max : datetime.timestamp
        _description_
    """

    # Compute the time difference
    time_range = max_date - min_date

    # Determine the minimum range
    if time_range < ONE_WEEK:
        min_range = min_date - (ONE_WEEK - time_range) / 2
        max_range = max_date + (ONE_WEEK - time_range) / 2
    elif time_range < ONE_MONTH:
        min_range = min_date - (ONE_MONTH - time_range) / 2
        max_range = max_date + (ONE_MONTH - time_range) / 2
    elif time_range < THREE_MONTHS:
        min_range = min_date - (THREE_MONTHS - time_range) / 2
        max_range = max_date + (THREE_MONTHS - time_range) / 2
    elif time_range < ONE_YEAR:
        min_range = min_date - (ONE_YEAR - time_range) / 2
        max_range = max_date + (ONE_YEAR - time_range) / 2
    elif time_range < TWO_YEARS:
        min_range = min_date - (TWO_YEARS - time_range) / 2
        max_range = max_date + (TWO_YEARS - time_range) / 2
    elif time_range < FIVE_YEARS:
        min_range = min_date - (FIVE_YEARS - time_range) / 2
        max_range = max_date + (FIVE_YEARS - time_range) / 2
    else:
        raise ValueError("Time range is too large")

    unit, format = range_unit_format(time_range)

    return min_range, max_range, unit, format


def df_timestamp_range(df, column="timestamp"):
    """Compute the min/max range of a timestamp column in a DataFrame

    Parameters
    ----------
    df : pd.DataFrame
        Must include a "timestamp" column

    Returns
    -------
    (min, max, time_unit, time_format)
        Minimum of range, maximum of range, and timestep unit and format
    """
    # Calculate min and max dates in the timestamp column
    min_date = df[column].min()
    max_date = df[column].max()

    return timestamp_range(min_date, max_date)


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


def bincount2D(x, y, xbin=0, ybin=0, xlim=None, ylim=None, weights=None):
    """
    Copied from: https://github.com/int-brain-lab/iblutil/blob/main/iblutil/numerical.py

    Computes a 2D histogram by aggregating values in a 2D array.

    :param x: values to bin along the 2nd dimension (c-contiguous)
    :param y: values to bin along the 1st dimension
    :param xbin:
        scalar: bin size along 2nd dimension
        0: aggregate according to unique values
        array: aggregate according to exact values (count reduce operation)
    :param ybin:
        scalar: bin size along 1st dimension
        0: aggregate according to unique values
        array: aggregate according to exact values (count reduce operation)
    :param xlim: (optional) 2 values (array or list) that restrict range along 2nd dimension
    :param ylim: (optional) 2 values (array or list) that restrict range along 1st dimension
    :param weights: (optional) defaults to None, weights to apply to each value for aggregation
    :return: 3 numpy arrays MAP [ny,nx] image, xscale [nx], yscale [ny]
    """
    # if no bounds provided, use min/max of vectors
    if xlim is None:
        xlim = [np.min(x), np.max(x)]
    if ylim is None:
        ylim = [np.min(y), np.max(y)]

    def _get_scale_and_indices(v, bin, lim):
        # if bin is a nonzero scalar, this is a bin size: create scale and indices
        if np.isscalar(bin) and bin != 0:
            scale = np.arange(lim[0], lim[1] + bin / 2, bin)
            ind = (np.floor((v - lim[0]) / bin)).astype(np.int64)
        # if bin == 0, aggregate over unique values
        else:
            scale, ind = np.unique(v, return_inverse=True)
        return scale, ind

    xscale, xind = _get_scale_and_indices(x, xbin, xlim)
    yscale, yind = _get_scale_and_indices(y, ybin, ylim)
    # aggregate by using bincount on absolute indices for a 2d array
    nx, ny = [xscale.size, yscale.size]
    ind2d = np.ravel_multi_index(np.c_[yind, xind].transpose(), dims=(ny, nx))
    r = np.bincount(ind2d, minlength=nx * ny, weights=weights).reshape(ny, nx)

    # if a set of specific values is requested output an array matching the scale dimensions
    if not np.isscalar(xbin) and xbin.size > 1:
        _, iout, ir = np.intersect1d(xbin, xscale, return_indices=True)
        _r = r.copy()
        r = np.zeros((ny, xbin.size))
        r[:, iout] = _r[:, ir]
        xscale = xbin

    if not np.isscalar(ybin) and ybin.size > 1:
        _, iout, ir = np.intersect1d(ybin, yscale, return_indices=True)
        _r = r.copy()
        r = np.zeros((ybin.size, r.shape[1]))
        r[iout, :] = _r[ir, :]
        yscale = ybin

    return r, xscale, yscale
