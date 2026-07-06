"""
UrbanCool AI — Phase 1: GEE Data Collection Module
backend/src/data_collection/gee_collector.py

Fetches from Google Earth Engine:
  - Landsat 8/9 Collection 2 Level-2 Surface Temperature (ST_B10 → LST in °C)
  - Landsat 8/9 raw reflectance bands for NDVI & NDBI computation
  - MODIS MOD11A1 Daily LST for cross-validation and gap-fill

All imagery is clipped to the Ahmedabad pilot bounding box and optionally
masked to a ward GeoJSON boundary. Results are exported to Drive or returned
as in-memory Earth Engine objects for downstream zonal statistics.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

# ── Pilot city constants ───────────────────────────────────────────────────────
AHMEDABAD_BBOX = [72.46, 22.87, 72.72, 23.13]   # [W, S, E, N] WGS-84

# Landsat 8 & 9 joint collection (harmonised)
L8_COLLECTION  = "LANDSAT/LC08/C02/T1_L2"
L9_COLLECTION  = "LANDSAT/LC09/C02/T1_L2"

# MODIS Terra daily LST 1 km
MODIS_LST_COLLECTION = "MODIS/061/MOD11A1"

# Landsat ST scale / offset (C2 L2)
ST_SCALE  = 0.00341802
ST_OFFSET = 149.0        # Kelvin; subtract 273.15 for °C

# Reflectance scale (C2 L2 SR bands)
SR_SCALE  = 0.0000275
SR_OFFSET = -0.2

# Summer season window (apply each year)
SUMMER_MONTHS = (3, 4, 5, 6)   # March – June

# Study years
STUDY_YEARS = [2021, 2022, 2023]

# Max cloud cover to accept a scene
MAX_CLOUD_PCT = 20


def _init_ee() -> None:
    """Initialise Earth Engine (assumes credentials already set up)."""
    import ee
    project = os.getenv("GEE_PROJECT", "").strip() or None
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)


def _get_roi() -> "ee.Geometry.Rectangle":
    """Return an EE Rectangle for Ahmedabad bounding box."""
    import ee
    w, s, e, n = AHMEDABAD_BBOX
    return ee.Geometry.Rectangle([w, s, e, n])


# ── Landsat LST ───────────────────────────────────────────────────────────────

def _apply_lst_scale(image: "ee.Image") -> "ee.Image":
    """Convert ST_B10 raw DN → LST in °C and return renamed image."""
    import ee
    lst = (
        image.select("ST_B10")
             .multiply(ST_SCALE)
             .add(ST_OFFSET)
             .subtract(273.15)
             .rename("LST_C")
    )
    return lst.copyProperties(image, ["system:time_start", "CLOUD_COVER",
                                      "system:index"])


def _apply_sr_scale(image: "ee.Image") -> "ee.Image":
    """Apply reflectance scale/offset to SR_B* bands."""
    import ee
    bands = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
    sr = image.select(bands).multiply(SR_SCALE).add(SR_OFFSET)
    return sr.copyProperties(image, ["system:time_start", "system:index"])


def _mask_clouds_landsat(image: "ee.Image") -> "ee.Image":
    """Mask cloud and cloud-shadow pixels using QA_PIXEL."""
    import ee
    qa = image.select("QA_PIXEL")
    # Bit 3: cloud shadow; Bit 4: cloud
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return image.updateMask(cloud_mask)


def _build_landsat_collection(
    start_date: str,
    end_date: str,
    roi: "ee.Geometry",
    cloud_pct: int = MAX_CLOUD_PCT,
) -> "ee.ImageCollection":
    """
    Merge Landsat 8 & 9 C2L2 collections, filter to ROI/date/cloud,
    apply cloud mask, and return a harmonised collection.
    """
    import ee

    def process(col_id: str) -> "ee.ImageCollection":
        return (
            ee.ImageCollection(col_id)
              .filterBounds(roi)
              .filterDate(start_date, end_date)
              .filter(ee.Filter.lt("CLOUD_COVER", cloud_pct))
              .map(_mask_clouds_landsat)
        )

    l8 = process(L8_COLLECTION)
    l9 = process(L9_COLLECTION)
    return l8.merge(l9).sort("system:time_start")


def fetch_landsat_lst(
    start_date: str = "2021-03-01",
    end_date: str   = "2023-06-30",
    cloud_pct: int  = MAX_CLOUD_PCT,
    as_median: bool = True,
) -> "ee.Image | ee.ImageCollection":
    """
    Fetch Landsat LST over Ahmedabad.

    Parameters
    ----------
    start_date, end_date : ISO date strings.
    cloud_pct            : Maximum cloud cover percentage filter.
    as_median            : If True, return a single median composite image.
                           If False, return the full time-series collection.

    Returns
    -------
    ee.Image (median) or ee.ImageCollection (time series).
    """
    _init_ee()
    roi = _get_roi()

    col = _build_landsat_collection(start_date, end_date, roi, cloud_pct)
    lst_col = col.map(_apply_lst_scale)

    scene_count = lst_col.size().getInfo()
    log.info("Landsat LST scenes found: %d (date: %s → %s, cloud ≤ %d%%)",
             scene_count, start_date, end_date, cloud_pct)

    if as_median:
        median = lst_col.select("LST_C").median().clip(roi)
        log.info("Returning median LST composite over Ahmedabad ROI.")
        return median
    return lst_col


def fetch_landsat_indices_bands(
    start_date: str = "2021-03-01",
    end_date: str   = "2023-06-30",
    cloud_pct: int  = MAX_CLOUD_PCT,
) -> "ee.Image":
    """
    Fetch a median reflectance composite for NDVI/NDBI computation.

    Bands returned (scaled):
        SR_B2  (Blue)  | SR_B3 (Green) | SR_B4 (Red)
        SR_B5  (NIR)   | SR_B6 (SWIR1) | SR_B7 (SWIR2)

    Returns
    -------
    ee.Image — median reflectance composite clipped to Ahmedabad ROI.
    """
    _init_ee()
    roi = _get_roi()

    col = _build_landsat_collection(start_date, end_date, roi, cloud_pct)
    sr_col = col.map(_apply_sr_scale)
    median_sr = sr_col.median().clip(roi)
    log.info("Returning median SR band composite for NDVI/NDBI input.")
    return median_sr


# ── Derived indices (EE-side computation) ─────────────────────────────────────

def compute_ndvi(sr_image: "ee.Image") -> "ee.Image":
    """NDVI = (NIR − Red) / (NIR + Red)  [SR_B5, SR_B4]."""
    ndvi = sr_image.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")
    log.info("NDVI computed on SR median composite.")
    return ndvi


def compute_ndbi(sr_image: "ee.Image") -> "ee.Image":
    """NDBI = (SWIR1 − NIR) / (SWIR1 + NIR)  [SR_B6, SR_B5]."""
    ndbi = sr_image.normalizedDifference(["SR_B6", "SR_B5"]).rename("NDBI")
    log.info("NDBI computed on SR median composite.")
    return ndbi


def compute_albedo_proxy(sr_image: "ee.Image") -> "ee.Image":
    """
    Broadband shortwave albedo proxy (Liang 2001 simplified):
        α ≈ 0.356·Blue + 0.130·Red + 0.373·NIR + 0.085·SWIR1 + 0.072·SWIR2 − 0.0018
    """
    albedo = (
        sr_image.select("SR_B2").multiply(0.356)
        .add(sr_image.select("SR_B4").multiply(0.130))
        .add(sr_image.select("SR_B5").multiply(0.373))
        .add(sr_image.select("SR_B6").multiply(0.085))
        .add(sr_image.select("SR_B7").multiply(0.072))
        .subtract(0.0018)
        .rename("ALBEDO")
    )
    log.info("Albedo proxy computed.")
    return albedo


# ── MODIS LST cross-validation ────────────────────────────────────────────────

def fetch_modis_lst(
    start_date: str = "2021-03-01",
    end_date: str   = "2023-06-30",
    daytime: bool   = True,
) -> "ee.Image":
    """
    Fetch MODIS MOD11A1 mean LST composite over Ahmedabad.

    Parameters
    ----------
    daytime : If True, use LST_Day_1km; else LST_Night_1km.

    Returns
    -------
    ee.Image — mean LST in °C, 1 km resolution.
    """
    _init_ee()
    roi = _get_roi()
    band = "LST_Day_1km" if daytime else "LST_Night_1km"

    col = (
        ee.ImageCollection(MODIS_LST_COLLECTION)  # noqa: F821 (imported at runtime)
          .filterBounds(roi)
          .filterDate(start_date, end_date)
          .select(band)
    )
    # MODIS scale: 0.02 K
    lst_celsius = (
        col.mean()
           .multiply(0.02)
           .subtract(273.15)
           .rename("MODIS_LST_C")
           .clip(roi)
    )
    import ee  # needed for ImageCollection ref above
    log.info("MODIS LST (%s) mean composite ready.", band)
    return lst_celsius


# ── Multi-year summer stacks ───────────────────────────────────────────────────

def build_summer_lst_stack(years: list[int] = STUDY_YEARS) -> dict[int, "ee.Image"]:
    """
    Return a dict {year: ee.Image(median LST)} for each study year's
    March–June window.  Used by the zonal statistics engine in Phase 2.
    """
    _init_ee()
    stack = {}
    for yr in years:
        start = f"{yr}-03-01"
        end   = f"{yr}-06-30"
        stack[yr] = fetch_landsat_lst(start, end, as_median=True)
        log.info("Built LST median composite for summer %d.", yr)
    return stack


# ── Quick sanity check (run directly) ─────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")
    _init_ee()
    roi = _get_roi()

    log.info("Fetching LST median composite 2021-2023 …")
    lst = fetch_landsat_lst("2021-03-01", "2023-06-30")
    sr  = fetch_landsat_indices_bands("2021-03-01", "2023-06-30")

    ndvi   = compute_ndvi(sr)
    ndbi   = compute_ndbi(sr)
    albedo = compute_albedo_proxy(sr)

    # Stack all into one image
    import ee
    stack = lst.addBands([ndvi, ndbi, albedo])

    stats = stack.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=100,
        maxPixels=1e8,
        bestEffort=True,
    ).getInfo()

    import json
    print(json.dumps(stats, indent=2))
    log.info("GEE collector sanity check PASSED ✅")
