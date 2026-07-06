"""
UrbanCool AI — Phase 2: OSM Vector Feature Metrics Engine
backend/src/features/osm_metrics.py

Computes the following per-ward metrics from OSM layers (all in UTM 43N):

Road metrics:
  - road_length_m         : Total road length within ward (m)
  - road_density_km_km2   : Road length per km² of ward area
  - road_area_m2          : Estimated road surface area (length × avg width proxy)
  - road_coverage_ratio   : road_area_m2 / ward_area_m2

Building metrics:
  - building_count        : Number of building footprints
  - building_density_km2  : Buildings per km²
  - built_area_m2         : Total footprint area within ward
  - built_area_ratio      : built_area_m2 / ward_area_m2

Water metrics:
  - water_area_m2         : Total water body area within ward
  - water_area_ratio      : water_area_m2 / ward_area_m2
  - water_proximity_m     : Distance from ward centroid to nearest water body (m)

Green space metrics:
  - green_area_m2         : Total green/park area within ward
  - green_area_ratio      : green_area_m2 / ward_area_m2
  - green_proximity_m     : Distance from ward centroid to nearest green space (m)

Urban Heat Island proxy:
  - impervious_proxy      : road_coverage_ratio + built_area_ratio (clipped to 1.0)
  - vegetation_deficit    : 1 - green_area_ratio (proxy for canopy gap)
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parents[2]
RAW_DIR       = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

TARGET_CRS = "EPSG:32643"

# Average road half-width per highway class (metres, one-side)
ROAD_WIDTH_MAP = {
    "motorway": 14.0,
    "trunk": 12.0,
    "primary": 10.0,
    "secondary": 8.0,
    "tertiary": 6.0,
    "residential": 5.0,
    "unclassified": 4.5,
    "service": 3.5,
    "track": 3.0,
    "default": 4.0,
}


def _load_utm(path: Path) -> gpd.GeoDataFrame | None:
    """Load a GeoJSON and reproject to UTM 43N, or return None if missing."""
    if not path.exists():
        log.warning("File not found: %s", path)
        return None
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(TARGET_CRS)


def _safe_overlay(source: gpd.GeoDataFrame,
                  wards: gpd.GeoDataFrame,
                  how: str = "intersection") -> gpd.GeoDataFrame:
    """Run a spatial overlay, catching empty-result edge cases."""
    try:
        result = gpd.overlay(source, wards[["ward_id","geometry"]], how=how)
        return result
    except Exception as exc:
        log.warning("Overlay failed (%s) — returning empty GDF.", exc)
        return gpd.GeoDataFrame(columns=source.columns.tolist() + ["ward_id"])


def _road_width(highway_val: str | None) -> float:
    """Estimate one-way road width from highway tag."""
    if not highway_val or highway_val == "nan":
        return ROAD_WIDTH_MAP["default"]
    # highway can be a pipe-joined string from Phase 1 flattening
    first = str(highway_val).split("|")[0].strip().lower()
    return ROAD_WIDTH_MAP.get(first, ROAD_WIDTH_MAP["default"])


# ═══════════════════════════════════════════════════════════════════════════════
# Metric computers
# ═══════════════════════════════════════════════════════════════════════════════

def compute_road_metrics(wards: gpd.GeoDataFrame,
                         roads: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return per-ward road metrics DataFrame."""
    log.info("Computing road metrics ...")

    # Keep only LineString roads (drop points/polygons if any)
    roads_line = roads[roads.geometry.geom_type.isin(
        ["LineString", "MultiLineString"]
    )].copy()

    # Clip roads to ward boundaries
    roads_clipped = gpd.clip(roads_line, wards.dissolve())
    roads_clipped["length_m"] = roads_clipped.geometry.length

    # Estimate road surface area using per-segment width
    if "highway" in roads_clipped.columns:
        roads_clipped["width_m"] = roads_clipped["highway"].apply(_road_width)
    else:
        roads_clipped["width_m"] = ROAD_WIDTH_MAP["default"]
    roads_clipped["road_area_m2"] = roads_clipped["length_m"] * roads_clipped["width_m"]

    # Spatial join road → ward
    roads_joined = gpd.sjoin(
        roads_clipped[["length_m","road_area_m2","geometry"]],
        wards[["ward_id","area_km2","geometry"]],
        how="inner",
        predicate="intersects",
    )

    road_agg = roads_joined.groupby("ward_id").agg(
        road_length_m   = ("length_m",   "sum"),
        road_area_m2    = ("road_area_m2","sum"),
    ).reset_index()

    result = wards[["ward_id","area_km2"]].merge(road_agg, on="ward_id", how="left")
    result["road_length_m"]       = result["road_length_m"].fillna(0).round(1)
    result["road_area_m2"]        = result["road_area_m2"].fillna(0).round(1)
    result["road_density_km_km2"] = (result["road_length_m"] / 1000 / result["area_km2"]).round(2)
    result["road_coverage_ratio"] = (result["road_area_m2"] /
                                     (result["area_km2"] * 1e6)).clip(0, 1).round(4)

    log.info("Road metrics computed for %d wards.", len(result))
    return result[["ward_id","road_length_m","road_density_km_km2",
                   "road_area_m2","road_coverage_ratio"]]


def compute_building_metrics(wards: gpd.GeoDataFrame,
                             buildings: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return per-ward building footprint metrics DataFrame."""
    log.info("Computing building metrics ...")

    bldgs_poly = buildings[buildings.geometry.geom_type.isin(
        ["Polygon","MultiPolygon"]
    )].copy()
    if bldgs_poly.crs != wards.crs:
        bldgs_poly = bldgs_poly.to_crs(wards.crs)

    # Clip to total city extent first (faster than per-ward)
    bldgs_clipped = gpd.clip(bldgs_poly, wards.dissolve())
    bldgs_clipped["footprint_m2"] = bldgs_clipped.geometry.area

    joined = gpd.sjoin(
        bldgs_clipped[["footprint_m2","geometry"]],
        wards[["ward_id","area_km2","geometry"]],
        how="inner",
        predicate="intersects",
    )

    bldg_agg = joined.groupby("ward_id").agg(
        building_count = ("footprint_m2","count"),
        built_area_m2  = ("footprint_m2","sum"),
    ).reset_index()

    result = wards[["ward_id","area_km2"]].merge(bldg_agg, on="ward_id", how="left")
    result["building_count"]      = result["building_count"].fillna(0).astype(int)
    result["built_area_m2"]       = result["built_area_m2"].fillna(0).round(1)
    result["building_density_km2"] = (result["building_count"] / result["area_km2"]).round(1)
    result["built_area_ratio"]    = (result["built_area_m2"] /
                                     (result["area_km2"] * 1e6)).clip(0, 1).round(4)

    log.info("Building metrics computed for %d wards.", len(result))
    return result[["ward_id","building_count","building_density_km2",
                   "built_area_m2","built_area_ratio"]]


def compute_water_metrics(wards: gpd.GeoDataFrame,
                          water: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return per-ward water body area and proximity metrics."""
    log.info("Computing water metrics ...")

    water_poly = water[water.geometry.geom_type.isin(
        ["Polygon","MultiPolygon","LineString","MultiLineString"]
    )].copy()
    if water_poly.crs != wards.crs:
        water_poly = water_poly.to_crs(wards.crs)

    # Clip polygon water bodies and compute area
    water_polys = water_poly[water_poly.geometry.geom_type.isin(
        ["Polygon","MultiPolygon"]
    )].copy()

    if not water_polys.empty:
        w_clipped = gpd.clip(water_polys, wards.dissolve())
        w_clipped["water_area_m2"] = w_clipped.geometry.area
        joined = gpd.sjoin(w_clipped[["water_area_m2","geometry"]],
                           wards[["ward_id","area_km2","geometry"]],
                           how="inner", predicate="intersects")
        water_agg = joined.groupby("ward_id").agg(
            water_area_m2=("water_area_m2","sum")
        ).reset_index()
    else:
        water_agg = pd.DataFrame(columns=["ward_id","water_area_m2"])

    # Proximity: distance from each ward centroid to nearest water feature
    ward_centroids = wards[["ward_id","geometry"]].copy()
    ward_centroids["centroid"] = wards.geometry.centroid
    centroids_gdf = gpd.GeoDataFrame(ward_centroids[["ward_id"]],
                                     geometry=ward_centroids["centroid"],
                                     crs=wards.crs)

    if not water_poly.empty:
        # Union all water geometries for nearest-distance computation
        water_union = unary_union(water_poly.geometry)
        centroids_gdf["water_proximity_m"] = centroids_gdf.geometry.apply(
            lambda p: p.distance(water_union)
        ).round(1)
    else:
        centroids_gdf["water_proximity_m"] = np.nan

    result = wards[["ward_id","area_km2"]].merge(water_agg, on="ward_id", how="left")
    result = result.merge(centroids_gdf[["ward_id","water_proximity_m"]],
                          on="ward_id", how="left")
    result["water_area_m2"]   = result["water_area_m2"].fillna(0).round(1)
    result["water_area_ratio"]= (result["water_area_m2"] /
                                  (result["area_km2"] * 1e6)).clip(0, 1).round(4)
    result["water_proximity_m"]= result["water_proximity_m"].fillna(9999).round(1)

    log.info("Water metrics computed for %d wards.", len(result))
    return result[["ward_id","water_area_m2","water_area_ratio","water_proximity_m"]]


def compute_green_metrics(wards: gpd.GeoDataFrame,
                          greenspace: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return per-ward green space area and proximity metrics."""
    log.info("Computing green space metrics ...")

    green_poly = greenspace[greenspace.geometry.geom_type.isin(
        ["Polygon","MultiPolygon"]
    )].copy()
    if green_poly.crs != wards.crs:
        green_poly = green_poly.to_crs(wards.crs)

    if not green_poly.empty:
        g_clipped = gpd.clip(green_poly, wards.dissolve())
        g_clipped["green_area_m2"] = g_clipped.geometry.area
        joined = gpd.sjoin(g_clipped[["green_area_m2","geometry"]],
                           wards[["ward_id","area_km2","geometry"]],
                           how="inner", predicate="intersects")
        green_agg = joined.groupby("ward_id").agg(
            green_area_m2=("green_area_m2","sum")
        ).reset_index()
    else:
        green_agg = pd.DataFrame(columns=["ward_id","green_area_m2"])

    # Proximity
    ward_centroids = wards[["ward_id","geometry"]].copy()
    ward_centroids["centroid"] = wards.geometry.centroid
    centroids_gdf = gpd.GeoDataFrame(ward_centroids[["ward_id"]],
                                     geometry=ward_centroids["centroid"],
                                     crs=wards.crs)

    if not green_poly.empty:
        green_union = unary_union(green_poly.geometry)
        centroids_gdf["green_proximity_m"] = centroids_gdf.geometry.apply(
            lambda p: p.distance(green_union)
        ).round(1)
    else:
        centroids_gdf["green_proximity_m"] = np.nan

    result = wards[["ward_id","area_km2"]].merge(green_agg, on="ward_id", how="left")
    result = result.merge(centroids_gdf[["ward_id","green_proximity_m"]],
                          on="ward_id", how="left")
    result["green_area_m2"]    = result["green_area_m2"].fillna(0).round(1)
    result["green_area_ratio"] = (result["green_area_m2"] /
                                   (result["area_km2"] * 1e6)).clip(0, 1).round(4)
    result["green_proximity_m"]= result["green_proximity_m"].fillna(9999).round(1)

    log.info("Green metrics computed for %d wards.", len(result))
    return result[["ward_id","green_area_m2","green_area_ratio","green_proximity_m"]]


# ═══════════════════════════════════════════════════════════════════════════════
# Master function
# ═══════════════════════════════════════════════════════════════════════════════

def compute_all_osm_metrics(
    wards: gpd.GeoDataFrame | None = None,
    save: bool = True,
) -> pd.DataFrame:
    """
    Compute all OSM-derived feature metrics for every ward.

    Parameters
    ----------
    wards : Ward GeoDataFrame in UTM 43N. If None, loaded from processed/.
    save  : Write result to data/processed/osm_ward_metrics.csv.

    Returns
    -------
    pd.DataFrame — one row per ward with all 14 OSM feature columns.
    """
    if wards is None:
        wards = gpd.read_file(PROCESSED_DIR / "wards.geojson").to_crs(TARGET_CRS)

    roads      = _load_utm(RAW_DIR / "osm_roads.geojson")
    buildings  = _load_utm(RAW_DIR / "osm_buildings.geojson")
    water      = _load_utm(RAW_DIR / "osm_water.geojson")
    greenspace = _load_utm(RAW_DIR / "osm_greenspace.geojson")

    df = wards[["ward_id","area_km2"]].copy()

    if roads is not None:
        df = df.merge(compute_road_metrics(wards, roads), on="ward_id", how="left")
    if buildings is not None:
        df = df.merge(compute_building_metrics(wards, buildings), on="ward_id", how="left")
    if water is not None:
        df = df.merge(compute_water_metrics(wards, water), on="ward_id", how="left")
    if greenspace is not None:
        df = df.merge(compute_green_metrics(wards, greenspace), on="ward_id", how="left")

    # ── Composite UHI proxies ─────────────────────────────────────────────────
    rc = df.get("road_coverage_ratio", pd.Series(0.0, index=df.index))
    ba = df.get("built_area_ratio",    pd.Series(0.0, index=df.index))
    gr = df.get("green_area_ratio",    pd.Series(0.0, index=df.index))

    df["impervious_proxy"]   = (rc.fillna(0) + ba.fillna(0)).clip(0, 1).round(4)
    df["vegetation_deficit"] = (1 - gr.fillna(0)).clip(0, 1).round(4)

    log.info("OSM metrics DataFrame: %d wards × %d features.", len(df), len(df.columns))

    if save:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out = PROCESSED_DIR / "osm_ward_metrics.csv"
        df.to_csv(out, index=False)
        log.info("Saved OSM metrics -> %s", out)

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")
    df = compute_all_osm_metrics()
    print(df[["ward_id","road_density_km_km2","building_density_km2",
              "green_area_ratio","impervious_proxy"]].head(10).to_string())
    log.info("OSM metrics PASSED")
