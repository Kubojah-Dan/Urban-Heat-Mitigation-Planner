"""
UrbanCool AI — Phase 2: Master Feature Builder
backend/src/features/feature_builder.py

Orchestrates the full preprocessing & feature engineering pipeline:

  Step 1 — CRS standardization (all layers → UTM 43N)
  Step 2 — GEE zonal statistics (LST, NDVI, NDBI, Albedo, MODIS LST)
  Step 3 — OSM vector metrics (road/building/water/green densities)
  Step 4 — Census join (population density, literacy, vulnerability proxies)
  Step 5 — Feature normalisation (min-max, store raw + normalised)
  Step 6 — Output: features_wards.csv + features_wards.geojson

Run from backend/:
    python -m src.features.feature_builder

    # Skip GEE (use cached gee_ward_stats.csv if it exists):
    python -m src.features.feature_builder --skip-gee

Output columns (one row per ward):
  ward_id, ward_name, area_km2,
  LST_mean, LST_std, LST_p90,
  NDVI_mean, NDBI_mean, ALBEDO_mean, MODIS_LST_mean,
  road_density_km_km2, road_coverage_ratio,
  building_density_km2, built_area_ratio,
  water_area_ratio, water_proximity_m,
  green_area_ratio, green_proximity_m,
  impervious_proxy, vegetation_deficit,
  population_total, pop_density_km2, child_ratio,
  literacy_rate, sc_st_ratio, non_worker_ratio,
  [all above normalised with _norm suffix]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Columns to normalise (0–1 min-max) for downstream ML/scoring
NORMALISE_COLS = [
    "LST_mean", "LST_p90",
    "NDVI_mean", "NDBI_mean", "ALBEDO_mean", "MODIS_LST_mean",
    "road_density_km_km2", "road_coverage_ratio",
    "building_density_km2", "built_area_ratio",
    "water_area_ratio", "water_proximity_m",
    "green_area_ratio", "green_proximity_m",
    "impervious_proxy", "vegetation_deficit",
    "pop_density_km2", "child_ratio", "sc_st_ratio", "non_worker_ratio",
]


def _load_census() -> pd.DataFrame:
    """Load processed census CSV."""
    path = PROCESSED_DIR / "census_wards.csv"
    if not path.exists():
        raise FileNotFoundError(f"Census data not found: {path}. Run collect_all first.")
    df = pd.read_csv(path)
    keep = ["ward_id","population_total","pop_density_km2",
            "child_ratio","literacy_rate","sc_st_ratio","non_worker_ratio"]
    return df[[c for c in keep if c in df.columns]]


def _load_gee_stats(skip: bool = False) -> pd.DataFrame | None:
    """Load cached GEE stats CSV or return None if skipped/missing."""
    path = PROCESSED_DIR / "gee_ward_stats.csv"
    if skip:
        log.info("GEE stats skipped by flag.")
        return None
    if path.exists():
        log.info("Loading cached GEE stats from %s", path)
        return pd.read_csv(path)
    return None


def _run_gee_stats(wards: gpd.GeoDataFrame) -> pd.DataFrame | None:
    """Run GEE zonal stats, return None on failure."""
    try:
        from src.features.gee_zonal_stats import compute_gee_ward_stats
        return compute_gee_ward_stats(ward_gdf=wards.to_crs("EPSG:4326"))
    except Exception as exc:
        log.error("GEE stats failed: %s — continuing without.", exc)
        return None


def _run_osm_metrics(wards_utm: gpd.GeoDataFrame) -> pd.DataFrame:
    """Run OSM metric computation."""
    from src.features.osm_metrics import compute_all_osm_metrics
    return compute_all_osm_metrics(wards=wards_utm)


def _normalise(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Apply MinMaxScaler to `cols` that exist in df.
    Adds `{col}_norm` columns (0–1 range).
    """
    available = [c for c in cols if c in df.columns and df[c].notna().any()]
    if not available:
        return df

    scaler = MinMaxScaler()
    df_norm = df.copy()
    df_norm[[f"{c}_norm" for c in available]] = scaler.fit_transform(
        df[available].fillna(df[available].median())
    ).round(4)
    log.info("Normalised %d feature columns.", len(available))
    return df_norm


def build_feature_table(
    skip_gee: bool = False,
    save: bool = True,
) -> pd.DataFrame:
    """
    Run the full Phase 2 feature engineering pipeline.

    Parameters
    ----------
    skip_gee : If True, skip GEE API calls (use cached file or omit).
    save     : Write outputs to data/processed/.

    Returns
    -------
    pd.DataFrame — one row per ward, all features + normalised variants.
    """
    log.info("=" * 60)
    log.info("  Phase 2: Feature Engineering Pipeline")
    log.info("=" * 60)

    # ── Step 1: Load ward boundaries in UTM 43N ───────────────────────────────
    log.info("[1/5] Loading ward boundaries ...")
    ward_path = PROCESSED_DIR / "wards.geojson"
    if not ward_path.exists():
        raise FileNotFoundError(
            "Ward boundaries not found. Run Phase 1 first: "
            "python -m src.data_collection.collect_all"
        )
    wards_wgs = gpd.read_file(ward_path)                        # EPSG:4326
    wards_utm = wards_wgs.to_crs("EPSG:32643")                 # UTM 43N
    log.info("Loaded %d wards.", len(wards_wgs))

    # Start feature table from ward identifiers
    features = wards_wgs[["ward_id","ward_name","area_km2"]].copy()

    # ── Step 2: GEE zonal statistics ─────────────────────────────────────────
    log.info("[2/5] GEE zonal statistics ...")
    gee_df = _load_gee_stats(skip=skip_gee)
    if gee_df is None and not skip_gee:
        gee_df = _run_gee_stats(wards_wgs)

    if gee_df is not None and "ward_id" in gee_df.columns:
        gee_cols = [c for c in gee_df.columns
                    if c.startswith(("LST","NDVI","NDBI","ALBEDO","MODIS"))]
        features = features.merge(gee_df[["ward_id"] + gee_cols],
                                  on="ward_id", how="left")
        log.info("GEE stats merged: %d columns.", len(gee_cols))
    else:
        log.warning("GEE stats unavailable — remote sensing columns will be NaN.")

    # ── Step 3: OSM vector metrics ────────────────────────────────────────────
    log.info("[3/5] OSM vector metrics ...")
    osm_df = _run_osm_metrics(wards_utm)
    osm_cols = [c for c in osm_df.columns if c not in ["ward_id","area_km2"]]
    features = features.merge(osm_df[["ward_id"] + osm_cols],
                              on="ward_id", how="left")
    log.info("OSM metrics merged: %d columns.", len(osm_cols))

    # ── Step 4: Census join ───────────────────────────────────────────────────
    log.info("[4/5] Joining Census data ...")
    census_df = _load_census()
    census_cols = [c for c in census_df.columns if c != "ward_id"]
    features = features.merge(census_df, on="ward_id", how="left")
    log.info("Census merged: %d columns.", len(census_cols))

    # ── Step 5: Normalisation ─────────────────────────────────────────────────
    log.info("[5/5] Normalising feature columns ...")
    features = _normalise(features, NORMALISE_COLS)

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("Feature table shape: %d rows × %d columns", *features.shape)
    log.info("Columns: %s", list(features.columns))

    # Fill remaining NaNs with column medians (for numeric columns only)
    num_cols = features.select_dtypes(include=["float64","int64"]).columns
    features[num_cols] = features[num_cols].fillna(features[num_cols].median())

    if save:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

        # CSV
        csv_path = PROCESSED_DIR / "features_wards.csv"
        features.to_csv(csv_path, index=False)
        log.info("Saved features CSV -> %s", csv_path)

        # GeoJSON (merge back with geometry for map rendering)
        geo_features = wards_wgs[["ward_id","geometry"]].merge(
            features, on="ward_id", how="inner"
        )
        geojson_path = PROCESSED_DIR / "features_wards.geojson"
        gpd.GeoDataFrame(geo_features, geometry="geometry",
                         crs="EPSG:4326").to_file(geojson_path, driver="GeoJSON")
        log.info("Saved features GeoJSON -> %s", geojson_path)

    return features


def print_sample_table(df: pd.DataFrame, n: int = 5) -> None:
    """Print a readable sample of the feature table."""
    display_cols = [
        "ward_id","ward_name",
        "LST_mean","NDVI_mean","NDBI_mean",
        "road_density_km_km2","built_area_ratio",
        "green_area_ratio","pop_density_km2",
    ]
    available = [c for c in display_cols if c in df.columns]
    print("\n" + "=" * 80)
    print("FEATURE TABLE SAMPLE (top 5 rows)")
    print("=" * 80)
    print(df[available].head(n).to_string(index=False))
    print(f"\nTotal wards: {len(df)} | Total features: {len(df.columns)}")

    # Quick stats
    num_cols = df.select_dtypes(include="number").columns
    null_pct = df[num_cols].isnull().mean().mean() * 100
    print(f"Numeric columns: {len(num_cols)} | Missing value rate: {null_pct:.1f}%")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(module)-22s | %(message)s",
    )

    parser = argparse.ArgumentParser(description="UrbanCool AI — Phase 2 Feature Builder")
    parser.add_argument("--skip-gee", action="store_true",
                        help="Skip GEE API calls (use cache or omit RS features)")
    args = parser.parse_args()

    df = build_feature_table(skip_gee=args.skip_gee)
    print_sample_table(df)
    log.info("Phase 2 feature pipeline COMPLETE")
    sys.exit(0)
