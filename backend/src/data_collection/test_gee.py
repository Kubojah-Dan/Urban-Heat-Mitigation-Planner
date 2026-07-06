"""
UrbanCool AI — Phase 0 GEE Connection Verification Script
backend/src/data_collection/test_gee.py

Purpose
-------
1. Authenticate with Google Earth Engine using a service-account key or
   the interactive `ee.Authenticate()` flow (configurable via env var).
2. Run a minimal diagnostic query: pull a single Landsat 8 Collection 2
   Level-2 surface-temperature band (ST_B10) over Ahmedabad's bounding box
   for a clear-sky scene in summer 2023.
3. Print band metadata and a sampled pixel value to confirm the pipeline
   is alive end-to-end.

Usage
-----
    # Option A — interactive browser auth (first-time setup)
    python test_gee.py

    # Option B — service-account (CI / headless)
    GEE_SERVICE_ACCOUNT=my@project.iam.gserviceaccount.com \
    GEE_KEY_FILE=/path/to/key.json \
    python test_gee.py

Environment Variables (all optional)
-------------------------------------
    GEE_SERVICE_ACCOUNT  : Service-account e-mail string.
    GEE_KEY_FILE         : Absolute path to the JSON private key file.
    GEE_PROJECT          : GEE Cloud project ID (required for new Earth
                           Engine API; set to your Google Cloud project).
"""

from __future__ import annotations

import os
import sys
import json
import logging

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gee_test")

# ── Constants — Ahmedabad pilot city ─────────────────────────────────────────
CITY_NAME = "Ahmedabad, India"

# Approximate bounding box for Ahmedabad municipal corporation area
# [west, south, east, north] in WGS-84 decimal degrees
AHMEDABAD_BBOX = [72.46, 22.87, 72.72, 23.13]

# Landsat 8 Collection 2 Level-2 — summer scene window
COLLECTION = "LANDSAT/LC08/C02/T1_L2"
DATE_START = "2023-04-01"
DATE_END   = "2023-06-30"

# ST_B10: Surface Temperature band (in scaled Kelvin; multiply by 0.00341802
# and add 149.0 to get Kelvin, then subtract 273.15 for Celsius)
SCALE_FACTOR = 0.00341802
OFFSET       = 149.0        # Kelvin


# ── Authentication helper ─────────────────────────────────────────────────────

def authenticate_gee() -> None:
    """
    Authenticate and initialise the Earth Engine API.

    Priority order:
      1. Service-account credentials (GEE_SERVICE_ACCOUNT + GEE_KEY_FILE).
      2. Previously cached interactive credentials (~/.config/earthengine/).
      3. Launch interactive browser-based OAuth2 flow.
    """
    import ee  # imported here so import errors surface cleanly

    service_account = os.getenv("GEE_SERVICE_ACCOUNT", "").strip()
    key_file        = os.getenv("GEE_KEY_FILE", "").strip()
    project         = os.getenv("GEE_PROJECT", "").strip() or None

    if service_account and key_file:
        log.info("Authenticating via service account: %s", service_account)
        credentials = ee.ServiceAccountCredentials(service_account, key_file)
        ee.Initialize(credentials=credentials, project=project)
        log.info("✅  Service-account authentication successful.")
        return

    # Try cached / interactive auth
    try:
        ee.Initialize(project=project)
        log.info("✅  Initialised with cached credentials.")
    except ee.EEException:
        log.info("No cached credentials found — launching browser auth …")
        ee.Authenticate()           # opens browser tab
        ee.Initialize(project=project)
        log.info("✅  Interactive authentication successful.")


# ── Diagnostic query ──────────────────────────────────────────────────────────

def run_diagnostic() -> dict:
    """
    Query one Landsat 8 LST scene over Ahmedabad and return a summary dict.
    """
    import ee

    west, south, east, north = AHMEDABAD_BBOX
    roi = ee.Geometry.Rectangle([west, south, east, north])

    log.info("Querying collection: %s", COLLECTION)
    log.info("Date range        : %s → %s", DATE_START, DATE_END)
    log.info("ROI               : %s", AHMEDABAD_BBOX)

    # ── 1. Filter to the least-cloudy summer scene ────────────────────────────
    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(roi)
        .filterDate(DATE_START, DATE_END)
        .filter(ee.Filter.lt("CLOUD_COVER", 20))
        .sort("CLOUD_COVER")
    )

    count = collection.size().getInfo()
    log.info("Scenes matching filter: %d", count)
    if count == 0:
        raise RuntimeError(
            "No Landsat 8 scenes found for the specified filters. "
            "Try relaxing the cloud-cover threshold or widening the date range."
        )

    # ── 2. Take the single clearest scene ────────────────────────────────────
    image = collection.first()
    image_id   = image.get("system:index").getInfo()
    cloud_pct  = image.get("CLOUD_COVER").getInfo()
    acq_date   = image.date().format("YYYY-MM-dd").getInfo()

    log.info("Selected scene: %s  |  date: %s  |  cloud: %.1f%%",
             image_id, acq_date, cloud_pct)

    # ── 3. Extract ST_B10 and convert to Celsius ──────────────────────────────
    st_band = image.select("ST_B10")

    # Apply scale factor → Kelvin → Celsius
    lst_celsius = st_band.multiply(SCALE_FACTOR).add(OFFSET).subtract(273.15)

    # ── 4. Compute mean LST over the ROI (sample statistic) ──────────────────
    stats = lst_celsius.reduceRegion(
        reducer   = ee.Reducer.mean().combine(
                        ee.Reducer.minMax(), sharedInputs=True),
        geometry  = roi,
        scale     = 100,          # 100 m resolution for speed
        maxPixels = 1e8,
        bestEffort= True,
    ).getInfo()

    mean_lst = stats.get("ST_B10_mean")
    min_lst  = stats.get("ST_B10_min")
    max_lst  = stats.get("ST_B10_max")

    log.info("── LST Statistics over Ahmedabad ROI ────────────────────────")
    log.info("  Mean LST : %.2f °C", mean_lst if mean_lst else float("nan"))
    log.info("  Min  LST : %.2f °C", min_lst  if min_lst  else float("nan"))
    log.info("  Max  LST : %.2f °C", max_lst  if max_lst  else float("nan"))

    # ── 5. Retrieve available band names ────────────────────────────────────
    bands = image.bandNames().getInfo()
    log.info("Available bands: %s", bands)

    result = {
        "status"       : "SUCCESS",
        "scene_id"     : image_id,
        "acquisition_date": acq_date,
        "cloud_cover_pct" : cloud_pct,
        "lst_mean_celsius": mean_lst,
        "lst_min_celsius" : min_lst,
        "lst_max_celsius" : max_lst,
        "available_bands" : bands,
        "roi_bbox"        : AHMEDABAD_BBOX,
        "collection"      : COLLECTION,
    }
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  UrbanCool AI — GEE Connection Diagnostic")
    log.info("  Pilot City  : %s", CITY_NAME)
    log.info("=" * 60)

    try:
        import ee
    except ImportError as exc:
        log.error(
            "earthengine-api not installed. Run:\n"
            "  pip install earthengine-api\n"
            "Error: %s", exc
        )
        sys.exit(1)

    # Step 1 — Authenticate
    try:
        authenticate_gee()
    except Exception as exc:
        log.error("Authentication failed: %s", exc)
        sys.exit(1)

    # Step 2 — Run diagnostic query
    try:
        result = run_diagnostic()
    except Exception as exc:
        log.error("Diagnostic query failed: %s", exc)
        sys.exit(1)

    # Step 3 — Pretty-print result summary
    log.info("=" * 60)
    log.info("  DIAGNOSTIC RESULT")
    log.info("=" * 60)
    print(json.dumps(result, indent=2))
    log.info("Phase 0 GEE verification PASSED ✅")


if __name__ == "__main__":
    main()
