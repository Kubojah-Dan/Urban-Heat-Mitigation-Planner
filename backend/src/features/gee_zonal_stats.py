"""
UrbanCool AI — Phase 2: GEE Zonal Statistics Engine
backend/src/features/gee_zonal_stats.py

For each AMC ward polygon, computes mean/std of:
  - LST_C      : Land Surface Temperature (°C) — Landsat 8/9 C2L2 summer median
  - NDVI       : Normalized Difference Vegetation Index
  - NDBI       : Normalized Difference Built-up Index
  - ALBEDO     : Broadband albedo proxy (Liang 2001)
  - MODIS_LST  : MODIS MOD11A1 daytime LST (°C) — cross-validation

Uses GEE's reduceRegions() with mean+stdDev reducers at 30 m scale for
Landsat-derived bands and 100 m for MODIS.

Output: data/processed/gee_ward_stats.csv
  One row per ward with columns:
    ward_id, LST_mean, LST_std, NDVI_mean, NDBI_mean,
    ALBEDO_mean, MODIS_LST_mean, LST_percentile_90
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# ── GEE constants (mirrors gee_collector.py) ──────────────────────────────────
L8_COLLECTION  = "LANDSAT/LC08/C02/T1_L2"
L9_COLLECTION  = "LANDSAT/LC09/C02/T1_L2"
MODIS_LST      = "MODIS/061/MOD11A1"

DATE_START = "2021-03-01"
DATE_END   = "2023-06-30"
CLOUD_PCT  = 20

ST_SCALE   = 0.00341802
ST_OFFSET  = 149.0
SR_SCALE   = 0.0000275
SR_OFFSET  = -0.2


# ── EE initialisation ─────────────────────────────────────────────────────────

def _init_ee():
    """
    Initialise Earth Engine, trying multiple strategies:
      1. ee.Initialize() with no project (uses GEE default / application-default creds)
      2. ee.Initialize(project=GEE_PROJECT) from env var
      3. ee.Authenticate() then retry
    This handles expired credentials and deleted projects gracefully.
    """
    import ee

    project = os.getenv("GEE_PROJECT", "").strip() or None

    # Strategy 1: try without explicit project (uses GEE's own default selection)
    try:
        ee.Initialize()
        log.info("EE initialised (no explicit project).")
        return
    except Exception as e1:
        log.debug("EE init without project failed: %s", e1)

    # Strategy 2: try with project from env var (if set)
    if project:
        try:
            ee.Initialize(project=project)
            log.info("EE initialised with project=%s", project)
            return
        except Exception as e2:
            log.warning("EE init with project=%s failed: %s", project, e2)

    # Strategy 3: re-authenticate and retry
    log.info("Attempting EE authentication ...")
    try:
        ee.Authenticate(auth_mode="notebook")   # non-blocking browser flow
    except Exception:
        ee.Authenticate()                        # standard browser flow

    if project:
        ee.Initialize(project=project)
    else:
        ee.Initialize()
    log.info("EE initialised after re-authentication.")


# ── Image preparation ─────────────────────────────────────────────────────────

def _build_landsat_composite():
    """
    Build a single multi-band median composite over 2021–2023 summers.
    Bands: LST_C, NDVI, NDBI, ALBEDO
    """
    import ee

    def mask_clouds(img):
        qa = img.select("QA_PIXEL")
        mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
        return img.updateMask(mask)

    def add_lst(img):
        lst = img.select("ST_B10").multiply(ST_SCALE).add(ST_OFFSET).subtract(273.15).rename("LST_C")
        return img.addBands(lst)

    def add_indices(img):
        sr = img.select(["SR_B2","SR_B3","SR_B4","SR_B5","SR_B6","SR_B7"]) \
                .multiply(SR_SCALE).add(SR_OFFSET)
        ndvi   = sr.normalizedDifference(["SR_B5","SR_B4"]).rename("NDVI")
        ndbi   = sr.normalizedDifference(["SR_B6","SR_B5"]).rename("NDBI")
        albedo = (sr.select("SR_B2").multiply(0.356)
                  .add(sr.select("SR_B4").multiply(0.130))
                  .add(sr.select("SR_B5").multiply(0.373))
                  .add(sr.select("SR_B6").multiply(0.085))
                  .add(sr.select("SR_B7").multiply(0.072))
                  .subtract(0.0018)
                  .rename("ALBEDO"))
        return img.addBands([ndvi, ndbi, albedo])

    l8 = (ee.ImageCollection(L8_COLLECTION)
            .filterDate(DATE_START, DATE_END)
            .filter(ee.Filter.lt("CLOUD_COVER", CLOUD_PCT))
            .map(mask_clouds).map(add_lst).map(add_indices))

    l9 = (ee.ImageCollection(L9_COLLECTION)
            .filterDate(DATE_START, DATE_END)
            .filter(ee.Filter.lt("CLOUD_COVER", CLOUD_PCT))
            .map(mask_clouds).map(add_lst).map(add_indices))

    merged = l8.merge(l9)
    composite = merged.select(["LST_C","NDVI","NDBI","ALBEDO"]).median()
    log.info("Landsat composite built (median 2021-2023 summers).")
    return composite


def _build_modis_composite():
    """MODIS MOD11A1 daytime mean LST in °C."""
    import ee
    return (ee.ImageCollection(MODIS_LST)
              .filterDate(DATE_START, DATE_END)
              .select("LST_Day_1km")
              .mean()
              .multiply(0.02).subtract(273.15)
              .rename("MODIS_LST"))


# ── Ward FeatureCollection ────────────────────────────────────────────────────

def _wards_to_ee_fc(ward_gdf: gpd.GeoDataFrame):
    """Convert ward GeoDataFrame (WGS-84) to ee.FeatureCollection."""
    import ee
    geojson = json.loads(ward_gdf.to_crs("EPSG:4326").to_json())
    features = []
    for feat in geojson["features"]:
        props = {k: v for k, v in feat["properties"].items()
                 if k != "geometry" and v is not None}
        geom = ee.Geometry(feat["geometry"])
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


# ── reduceRegions wrapper ─────────────────────────────────────────────────────

def _reduce_image_to_wards(
    image,
    fc,
    scale: int,
    reducer_name: str = "mean_stdDev",
) -> pd.DataFrame:
    """
    Run image.reduceRegions() and return a clean DataFrame.
    """
    import ee

    reducer = ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)

    result = image.reduceRegions(
        collection = fc,
        reducer    = reducer,
        scale      = scale,
        crs        = "EPSG:32643",
    )

    features = result.getInfo()["features"]
    rows = []
    for feat in features:
        props = feat.get("properties", {})
        rows.append(props)
    df = pd.DataFrame(rows)
    log.info("reduceRegions returned %d rows, %d columns.", len(df), len(df.columns))
    return df


# ── LST percentile (heat-tail measure) ───────────────────────────────────────

def _compute_lst_percentile(composite, fc, percentile: int = 90) -> pd.DataFrame:
    """Compute pXX LST per ward."""
    import ee
    reducer = ee.Reducer.percentile([percentile])
    result  = composite.select("LST_C").reduceRegions(
        collection=fc, reducer=reducer, scale=30, crs="EPSG:32643"
    )
    rows = [f["properties"] for f in result.getInfo()["features"]]
    df   = pd.DataFrame(rows)
    p_col = [c for c in df.columns if str(percentile) in c]
    if p_col:
        df = df.rename(columns={p_col[0]: f"LST_p{percentile}"})
    return df[[c for c in ["ward_id", f"LST_p{percentile}"] if c in df.columns]]


# ── Main public function ──────────────────────────────────────────────────────

def compute_gee_ward_stats(
    ward_gdf: gpd.GeoDataFrame | None = None,
    save: bool = True,
) -> pd.DataFrame:
    """
    Compute GEE-derived zonal statistics per AMC ward.

    Parameters
    ----------
    ward_gdf : Ward GeoDataFrame (EPSG:4326). If None, loaded from processed/.
    save     : Write result to data/processed/gee_ward_stats.csv.

    Returns
    -------
    pd.DataFrame — one row per ward with LST/NDVI/NDBI/ALBEDO/MODIS stats.
    """
    _init_ee()

    if ward_gdf is None:
        ward_gdf = gpd.read_file(PROCESSED_DIR / "wards.geojson")

    # Ensure WGS-84 for GEE upload
    ward_wgs = ward_gdf.to_crs("EPSG:4326")
    fc = _wards_to_ee_fc(ward_wgs)
    log.info("Ward FeatureCollection created: %d features.", len(ward_wgs))

    # ── Landsat composite stats ───────────────────────────────────────────────
    log.info("Computing Landsat zonal statistics (scale=30m) ...")
    composite = _build_landsat_composite()
    df_landsat = _reduce_image_to_wards(composite, fc, scale=30)

    # Rename mean/stdDev columns to explicit names
    rename_map = {}
    for band in ["LST_C","NDVI","NDBI","ALBEDO"]:
        for suffix, new_suffix in [("_mean","_mean"),("_stdDev","_std")]:
            old = f"{band}{suffix}"
            new = f"{band.replace('_C','')}{new_suffix}" if band == "LST_C" else f"{band}{new_suffix}"
            if old in df_landsat.columns:
                rename_map[old] = new
    # Handle simple 'mean'/'stdDev' column names (when single band was selected)
    if "mean" in df_landsat.columns:
        rename_map["mean"] = "LST_mean"
    if "stdDev" in df_landsat.columns:
        rename_map["stdDev"] = "LST_std"
    df_landsat = df_landsat.rename(columns=rename_map)

    # ── LST p90 ───────────────────────────────────────────────────────────────
    log.info("Computing LST p90 per ward ...")
    df_p90 = _compute_lst_percentile(composite, fc, percentile=90)

    # ── MODIS LST stats ───────────────────────────────────────────────────────
    log.info("Computing MODIS LST zonal statistics (scale=100m) ...")
    modis = _build_modis_composite()
    df_modis = _reduce_image_to_wards(modis, fc, scale=100)
    modis_rename = {}
    for col in df_modis.columns:
        if "mean" in col.lower():
            modis_rename[col] = "MODIS_LST_mean"
        elif "std" in col.lower():
            modis_rename[col] = "MODIS_LST_std"
    df_modis = df_modis.rename(columns=modis_rename)

    # ── Merge all stats ───────────────────────────────────────────────────────
    # ward_id is preserved as a property through EE
    id_col = "ward_id"

    # Identify join key — GEE may return it as 'ward_id' or nested differently
    for df_ in [df_landsat, df_modis, df_p90]:
        if id_col not in df_.columns:
            # Try integer-based index fallback
            df_.reset_index(drop=True, inplace=True)
            df_[id_col] = ward_wgs[id_col].values[:len(df_)]

    stats = df_landsat.copy()

    # Merge MODIS
    modis_cols = [id_col] + [c for c in df_modis.columns
                              if c.startswith("MODIS") and c != id_col]
    if set(modis_cols).issubset(df_modis.columns):
        stats = stats.merge(df_modis[modis_cols], on=id_col, how="left")

    # Merge p90
    if id_col in df_p90.columns and "LST_p90" in df_p90.columns:
        stats = stats.merge(df_p90[[id_col,"LST_p90"]], on=id_col, how="left")

    # Round float columns
    float_cols = stats.select_dtypes(include="float64").columns
    stats[float_cols] = stats[float_cols].round(4)

    log.info("GEE ward stats shape: %s", stats.shape)

    if save:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out = PROCESSED_DIR / "gee_ward_stats.csv"
        stats.to_csv(out, index=False)
        log.info("Saved GEE stats -> %s", out)

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")
    df = compute_gee_ward_stats()
    print(df[["ward_id","LST_mean","NDVI_mean","NDBI_mean","ALBEDO_mean"]].head(10).to_string())
    log.info("GEE zonal stats PASSED")
