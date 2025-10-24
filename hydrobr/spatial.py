"""Lightweight spatial operations (basins, land-use)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point


def find_basin_by_point(
    latitude: float,
    longitude: float,
    shapefile_path: str | Path,
    *,
    columns: list[str] | None = None,
) -> gpd.GeoDataFrame:
    """Select the Otto basin polygon that contains the provided point."""

    gdf = gpd.read_file(shapefile_path)
    if gdf.crs is None:
        raise ValueError("Shapefile has no CRS defined.")
    point = Point(float(longitude), float(latitude))
    point_gdf = gpd.GeoSeries([point], crs="EPSG:4326")
    if gdf.crs.to_epsg() != 4326:
        point_gdf = point_gdf.to_crs(gdf.crs)
    mask = gdf.contains(point_gdf.iloc[0])
    basin = gdf.loc[mask]
    if basin.empty:
        raise ValueError("No basin polygon found for the provided point.")
    if columns:
        keep = [col for col in columns if col in basin.columns] + [gdf.geometry.name]
        basin = basin[keep]
    basin.attrs["method"] = "otto_point_intersection"
    return basin


def delineate_basin_from_dem(
    dem_path: str | Path,
    latitude: float,
    longitude: float,
    *,
    method: str = "pysheds",
) -> gpd.GeoDataFrame:
    """Delineate watershed from a DEM using pysheds or richdem."""

    if method == "pysheds":
        try:
            from pysheds.grid import Grid  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("pysheds not installed. Run `pip install hydrobr[geo]`.") from exc

        grid = Grid.from_raster(str(dem_path))
        dem = grid.read_raster(str(dem_path))
        grid.fill_depressions(dem, in_place=True)
        grid.resolve_flats(dem, in_place=True)
        fdir = grid.flowdir(data=dem, dirmap=grid.d8)
        row, col = grid.nearest_cell(longitude, latitude)
        catch = grid.catchment(x=col, y=row, fdir=fdir, dirmap=grid.d8)
        shapes = list(grid.polygonize(catch))
        if not shapes:
            raise ValueError("Could not delineate basin using pysheds.")
        gdf = gpd.GeoDataFrame(geometry=[shapes[0][0]], crs=grid.crs)
        gdf.attrs["method"] = "pysheds"
        return gdf

    if method == "richdem":
        try:
            import richdem as rd  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("richdem not installed. Run `pip install hydrobr[geo]`.") from exc

        dem = rd.LoadGDAL(str(dem_path))
        filled = rd.FillDepressions(dem, epsilon=True)
        _ = rd.FlowDirectionD8(filled)
        raise NotImplementedError("RichDEM-based delineation pipeline still pending implementation.")

    raise ValueError(f"Unknown method: {method}")


def characterize_basin(
    basin: gpd.GeoDataFrame,
    drainage: gpd.GeoDataFrame | None = None,
) -> dict[str, float]:
    """Calculate basic basin metrics (area, perimeter, drainage density)."""

    if basin.crs is None:
        raise ValueError("Basin GeoDataFrame has no CRS defined.")
    basin_metric = basin.to_crs(epsg=3857)
    area_km2 = float(basin_metric.area.sum() / 1e6)
    perimeter_km = float(basin_metric.length.sum() / 1000)
    metrics: dict[str, float] = {"area_km2": area_km2, "perimeter_km": perimeter_km}

    if drainage is not None:
        if drainage.crs != basin.crs:
            drainage = drainage.to_crs(basin.crs)
        drainage_metric = drainage.to_crs(epsg=3857)
        total_length_km = float(drainage_metric.length.sum() / 1000)
        metrics["total_drainage_length_km"] = total_length_km
        if area_km2 > 0:
            metrics["drainage_density_km_km2"] = total_length_km / area_km2
        if {"elev_start", "elev_end"}.issubset(drainage.columns):
            slopes = (drainage["elev_start"] - drainage["elev_end"]) / drainage_metric.length
            metrics["mean_segment_slope"] = float(slopes.mean())
    return metrics


def summarize_land_use(
    raster_path: str | Path,
    basin: gpd.GeoDataFrame,
    *,
    class_labels: dict[int, str] | None = None,
) -> gpd.GeoDataFrame:
    """Compute land-use area by class within the basin polygon."""

    import numpy as np
    import pandas as pd
    import rasterio
    from rasterio.mask import mask

    if basin.crs is None:
        raise ValueError("Basin GeoDataFrame has no CRS defined.")

    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise ValueError("Raster has no CRS defined.")
        if src.crs != basin.crs:
            basin = basin.to_crs(src.crs)
        geometry = [geom for geom in basin.geometry]
        data, _ = mask(src, geometry, crop=True)
        values = data[0]
        values = values[values != src.nodata]
        pixel_area = abs(src.transform[0]) * abs(src.transform[4])

    unique, counts = np.unique(values, return_counts=True)
    area_m2 = counts * pixel_area
    df = pd.DataFrame({"class": unique.astype(int), "area_m2": area_m2})
    if class_labels:
        df["label"] = df["class"].map(class_labels)
    df["area_km2"] = df["area_m2"] / 1e6
    df.attrs["method"] = "land_use_summary"
    return df
