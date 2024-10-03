import panel as pn

import numpy as np
import altair as alt
import pandas as pd

from zombie.utils import bincount2D


@pn.cache()
def raster_aggregated(
    sx,
    sy,
    zoom_window=None,
    t_bins=1000,
    d_bins=394 / 2,
    width=800,
    height=400,
):
    """Generate a raster plot of events with Altair as the backend

    This function aggregates data into time bins and depth bins

    Parameters
    ----------
    sx : event times
        For example, spike times or indexes
    sy : event heights
        For example, spike depths on probe
    zoom_window : tuple, optional
        Minimum and maximum event time bounds, by default None
    t_bins : int, optional
        Number of time bins, rasters will look best if t_bins is roughly the pixel width +100, by default 1000
    d_bins : _type_, optional
        Number of depth bins, rasters will look best if this is roughly the number of channels on a probe, by default 394/2

    Returns
    -------
    alt.Chart
        Raster plot Altair chart
    """

    if not zoom_window:
        # define zoom_window from min/max values
        zoom_window = (np.min(sx), np.max(sx))

    dt = (zoom_window[1] - zoom_window[0]) / t_bins
    dd = (np.max(sy) - np.min(sy)) / d_bins

    # x, y = np.meshgrid(np.)
    raster, xscale, yscale = bincount2D(sx, sy, xbin=dt, ybin=dd)
    x, y = np.meshgrid(xscale, yscale)

    df = pd.DataFrame(
        data={"time": x.ravel(), "depth": y.ravel(), "count": raster.ravel()}
    )

    raster_plot = (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X(
                "time:O",
                axis=alt.Axis(
                    values=[xscale[1], xscale[-1]],
                    format=".0f",
                    title="Time (index)",
                ),
            ),
            y=alt.Y(
                "depth:O",
                axis=alt.Axis(
                    values=[yscale[1], yscale[-1]],
                    format=".0f",
                    tickCount=10,
                    title="Depth on probe (um)",
                ),
            ),
            color=alt.Color(
                "count:Q", scale=alt.Scale(range=["white", "black"])
            ),
        )
        .properties(width=width, height=height)
    )

    return raster_plot


@pn.cache()
def raster_points(sx, sy, scolor=None, colormap=None):
    """Generate a raster plot using individual marks for each spike

    Parameters
    ----------
    sx : _type_
        _description_
    sy : _type_
        _description_
    scolor : _type_, optional
        _description_, by default None
    colormap : _type_, optional
        _description_, by default None
    """
