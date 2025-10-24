"""Quick visualization helpers built with Plotly and Folium."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import processing


def plot_flow_duration_curve(data: pd.DataFrame) -> go.Figure:
    """Create a flow duration curve figure."""

    fdc = processing.compute_flow_duration_curve(data)
    fig = go.Figure()
    for column in fdc.columns:
        fig.add_trace(go.Scatter(x=fdc.index, y=fdc[column], mode="lines", name=str(column)))
    fig.update_layout(
        xaxis_title="Exceedance (%)",
        yaxis_title="Discharge",
        template="plotly_white",
    )
    return fig


def plot_gantt(data: pd.DataFrame, *, monthly: bool = True) -> go.Figure:
    """Build a availability Gantt chart."""

    if monthly:
        availability = data.notna().groupby(pd.Grouper(freq="MS")).sum() > 0
    else:
        availability = data.notna()
    records = []
    for column in data.columns:
        serie = availability[column]
        if not serie.any():
            continue
        serie = serie.astype(int)
        diffs = serie.diff().fillna(serie.iloc[0])
        starts = diffs[diffs == 1].index
        ends = diffs[diffs == -1].index
        if serie.iloc[0] == 1:
            starts = starts.insert(0, serie.index[0])
        if serie.iloc[-1] == 1:
            ends = ends.append(pd.Index([serie.index[-1]]))
        for start, end in zip(starts, ends):
            records.append({"Station": column, "Start": start, "Finish": end})
    if not records:
        raise ValueError("No data available to build the Gantt chart.")
    df = pd.DataFrame(records)
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Station", color="Station")
    fig.update_layout(template="plotly_white")
    return fig


def plot_operating_stations(data: pd.DataFrame) -> go.Figure:
    """Bar chart with the count of operating stations per year."""

    counts = data.notna().groupby(data.index.year).sum() > 0
    total = counts.sum(axis=1)
    fig = px.bar(x=total.index, y=total.values, labels={"x": "Year", "y": "Stations"})
    fig.update_layout(template="plotly_white")
    return fig


def plot_hyetograph(data: pd.Series | pd.DataFrame) -> go.Figure:
    """Generate a daily precipitation bar chart."""

    df = data.to_frame() if isinstance(data, pd.Series) else data
    fig = go.Figure()
    for column in df.columns:
        fig.add_bar(x=df.index, y=df[column], name=str(column))
    fig.update_layout(
        barmode="overlay",
        xaxis_title="Date",
        yaxis_title="Precipitation (mm)",
        template="plotly_white",
    )
    return fig


def plot_map(gdf: "geopandas.GeoDataFrame") -> "folium.Map":
    """Generate a quick Folium map from a GeoDataFrame."""

    import folium  # noqa: WPS433

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326, allow_override=True)
    center = gdf.to_crs(epsg=4326).geometry.unary_union.centroid
    fmap = folium.Map(location=[center.y, center.x], zoom_start=6)
    folium.GeoJson(gdf.to_json()).add_to(fmap)
    return fmap
