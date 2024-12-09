from datetime import timedelta

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


def format_link(link: str, text: str = "link"):
    """Format link as an HTML anchor tag

    Parameters
    ----------
    link : str
    text : str, optional
        by default "link"
    """
    return f'<a href="{link}" target="_blank">{text}</a>'


def set_background():
    """Set the background color of the Panel app"""
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
    pn.config.raw_css.append(BACKGROUND_CSS)


def status_html(status: Status):
    print(status)
    if status == Status.PASS:
        color = AIND_COLORS["green"]
    elif status == Status.PENDING:
        color = AIND_COLORS["light_blue"]
    elif status == Status.FAIL:
        color = AIND_COLORS["red"]
    else:
        color = "#756575"

    return f'<span style="color:{color};">{status.value}</span>'


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

    # Compute the time difference
    time_range = max_date - min_date

    # Define minimum ranges based on your criteria
    one_week = timedelta(weeks=1)
    one_month = timedelta(days=30)
    three_months = timedelta(days=90)
    one_year = timedelta(days=365)

    # Determine the minimum range
    if time_range < one_week:
        min_range = min_date - (one_week - time_range) / 2
        max_range = max_date + (one_week - time_range) / 2
        unit = "day"
        format = "%b %d"
    elif time_range < one_month:
        min_range = min_date - (one_month - time_range) / 2
        max_range = max_date + (one_month - time_range) / 2
        unit = "week"
        format = "%b %d"
    elif time_range < three_months:
        min_range = min_date - (three_months - time_range) / 2
        max_range = max_date + (three_months - time_range) / 2
        unit = "week"
        format = "%b %d"
    else:
        min_range = min_date - (one_year - time_range) / 2
        max_range = max_date + (one_year - time_range) / 2
        unit = "month"
        format = "%b"

    return (min_range, max_range, unit, format)


def md_style(font_size: int = 12, inner_str: str = ""):
    return f'<span style="font-size:{font_size}pt">{inner_str}</span>'


def qc_color(v):
    """Re-color the QC field background

    Parameters
    ----------
    v : str
        QC status value

    Returns
    -------
    str
        CSS style string
    """
    if v == "No QC":
        color = AIND_COLORS["yellow"]
    elif v == "Pass":
        color = AIND_COLORS["green"]
    elif v == "Fail":
        color = AIND_COLORS["red"]
    elif v == "Pending":
        color = AIND_COLORS["light_blue"]
    else:
        color = AIND_COLORS["grey"]
    return f"background-color: {color}"


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
