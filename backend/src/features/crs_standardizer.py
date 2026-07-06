"""
UrbanCool AI — Phase 2: CRS Standardizer
backend/src/features/crs_standardizer.py

Reprojects all raw spatial files to UTM Zone 43N (EPSG:32643),
the metric CRS appropriate for Ahmedabad (central meridian 75°E).
Also validates geometry validity and fixes minor topology issues.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
from shapely.validation import make_valid

log = logging.getLogger(__name__)

TARGET_CRS = "EPSG:32643"     # UTM Zone 43N
WGS84_CRS  = "EPSG:4326"

BASE_DIR      = Path(__file__).resolve().parents[2]
RAW_DIR       = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
BOUNDARIES_DIR = BASE_DIR / "data" / "boundaries"


def _fix_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Apply make_valid() to any invalid geometries."""
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        count = int(invalid.sum())
        log.warning("Fixing %d invalid geometries ...", count)
        gdf = gdf.copy()
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].apply(make_valid)
    return gdf


def reproject(
    gdf: gpd.GeoDataFrame,
    target_crs: str = TARGET_CRS,
    fix_geoms: bool = True,
) -> gpd.GeoDataFrame:
    """
    Reproject a GeoDataFrame to target_crs.

    Parameters
    ----------
    gdf        : Input GeoDataFrame (any CRS).
    target_crs : Target EPSG string, default EPSG:32643.
    fix_geoms  : Apply make_valid() before reprojection.

    Returns
    -------
    GeoDataFrame in target_crs.
    """
    if gdf.crs is None:
        log.warning("GeoDataFrame has no CRS — assuming EPSG:4326.")
        gdf = gdf.set_crs(WGS84_CRS)
    if fix_geoms:
        gdf = _fix_geometries(gdf)
    if str(gdf.crs) == target_crs:
        return gdf
    out = gdf.to_crs(target_crs)
    log.info("Reprojected %d features: %s → %s", len(out), gdf.crs, target_crs)
    return out


def load_and_reproject(path: Path, target_crs: str = TARGET_CRS) -> gpd.GeoDataFrame:
    """Load a GeoJSON/Shapefile and reproject to target_crs."""
    gdf = gpd.read_file(path)
    return reproject(gdf, target_crs)


def load_all_layers_utm() -> dict[str, gpd.GeoDataFrame]:
    """
    Load all raw OSM layers and the ward boundaries, returning each
    reprojected to UTM 43N (EPSG:32643).

    Returns
    -------
    {
        "wards"      : GeoDataFrame,
        "roads"      : GeoDataFrame,
        "buildings"  : GeoDataFrame,
        "water"      : GeoDataFrame,
        "greenspace" : GeoDataFrame,
    }
    """
    files = {
        "wards"      : PROCESSED_DIR / "wards.geojson",
        "roads"      : RAW_DIR       / "osm_roads.geojson",
        "buildings"  : RAW_DIR       / "osm_buildings.geojson",
        "water"      : RAW_DIR       / "osm_water.geojson",
        "greenspace" : RAW_DIR       / "osm_greenspace.geojson",
    }
    layers: dict[str, gpd.GeoDataFrame] = {}
    for name, path in files.items():
        if not path.exists():
            log.warning("Layer '%s' not found at %s — skipping.", name, path)
            continue
        gdf = load_and_reproject(path)
        layers[name] = gdf
        log.info("Loaded %-12s | %d features | CRS: %s", name, len(gdf), gdf.crs)
    return layers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")
    layers = load_all_layers_utm()
    for name, gdf in layers.items():
        print(f"{name}: {len(gdf)} | bounds: {gdf.total_bounds.round(0)}")
