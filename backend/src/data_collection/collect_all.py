"""
UrbanCool AI — Phase 1: Master Data Collection Orchestrator
backend/src/data_collection/collect_all.py

Single entry point that runs all Phase 1 data collection tasks in sequence:
  1. Ward boundaries & census data (boundary_loader)
  2. Open-Meteo historical weather (weather_collector)
  3. OSM geospatial layers (osm_collector)
  4. GEE remote sensing data (gee_collector)
     — LST median composite
     — SR bands for NDVI/NDBI
     — MODIS LST cross-validation

Run from backend/:
    python -m src.data_collection.collect_all

All raw outputs land in data/raw/
Processed wards/census → data/processed/

Environment variables:
    GEE_PROJECT  — Google Cloud project ID (required for GEE tasks)
    GEE_SERVICE_ACCOUNT, GEE_KEY_FILE — optional service account auth
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(module)-22s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Result accumulator ────────────────────────────────────────────────────────
RESULTS: dict[str, dict] = {}


def _step(name: str, fn, *args, **kwargs) -> bool:
    """Run a collection step, catch errors, and record status."""
    log.info("=" * 60)
    log.info("  STEP: %s", name)
    log.info("=" * 60)
    try:
        result = fn(*args, **kwargs)
        RESULTS[name] = {"status": "SUCCESS", "detail": str(result)[:200]}
        log.info("✅  %s — DONE", name)
        return True
    except Exception as exc:
        log.error("❌  %s — FAILED: %s", name, exc, exc_info=True)
        RESULTS[name] = {"status": "FAILED", "error": str(exc)}
        return False


def run_all(
    skip_osm: bool    = False,
    skip_gee: bool    = False,
    skip_weather: bool = False,
) -> dict:
    """
    Execute all Phase 1 collection tasks.

    Parameters
    ----------
    skip_osm     : Skip OSM download (useful if already cached in raw/).
    skip_gee     : Skip GEE remote sensing (useful in offline testing).
    skip_weather : Skip Open-Meteo fetch.

    Returns
    -------
    dict — per-step status summary.
    """
    from src.data_collection.boundary_loader import (
        load_ward_boundaries, load_census_data,
        save_processed_boundaries, save_census_csv,
    )
    from src.data_collection.weather_collector import fetch_weather
    from src.data_collection.osm_collector import fetch_all_osm_layers
    from src.data_collection.gee_collector import (
        fetch_landsat_lst,
        fetch_landsat_indices_bands,
        compute_ndvi, compute_ndbi, compute_albedo_proxy,
        fetch_modis_lst,
    )

    # ── Task 1: Ward boundaries ───────────────────────────────────────────────
    wards = None

    def _load_boundaries():
        nonlocal wards
        wards = load_ward_boundaries()
        save_processed_boundaries(wards)
        return f"{len(wards)} wards loaded"

    _step("Ward Boundaries", _load_boundaries)

    # ── Task 2: Census data ───────────────────────────────────────────────────
    def _load_census():
        census = load_census_data(wards)
        save_census_csv(census)
        return f"{len(census)} ward census rows"

    _step("Census Data", _load_census)

    # ── Task 3: Weather (Open-Meteo) ──────────────────────────────────────────
    if not skip_weather:
        def _fetch_weather():
            df = fetch_weather()
            return f"{len(df)} hourly records"
        _step("Open-Meteo Weather", _fetch_weather)
    else:
        log.info("SKIPPED: Open-Meteo Weather")

    # ── Task 4: OSM layers ────────────────────────────────────────────────────
    if not skip_osm:
        def _fetch_osm():
            layers = fetch_all_osm_layers()
            return {k: len(v) for k, v in layers.items()}
        _step("OSM Layers (roads/buildings/water/green)", _fetch_osm)
    else:
        log.info("SKIPPED: OSM Layers")

    # ── Task 5: GEE remote sensing ────────────────────────────────────────────
    if not skip_gee:
        def _fetch_gee():
            import ee
            project = os.getenv("GEE_PROJECT", "").strip() or None
            try:
                ee.Initialize(project=project)
            except Exception:
                ee.Authenticate()
                ee.Initialize(project=project)

            roi = ee.Geometry.Rectangle([72.46, 22.87, 72.72, 23.13])

            # LST median composite
            lst = fetch_landsat_lst("2021-03-01", "2023-06-30", as_median=True)

            # SR bands for index computation
            sr  = fetch_landsat_indices_bands("2021-03-01", "2023-06-30")
            ndvi   = compute_ndvi(sr)
            ndbi   = compute_ndbi(sr)
            albedo = compute_albedo_proxy(sr)

            # MODIS cross-validation
            modis = fetch_modis_lst("2021-03-01", "2023-06-30")

            # Quick stats check
            stack = lst.addBands([ndvi, ndbi, albedo, modis])
            stats = stack.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=roi,
                scale=100,
                maxPixels=1e8,
                bestEffort=True,
            ).getInfo()
            return stats

        _step("GEE Remote Sensing (LST/NDVI/NDBI/Albedo/MODIS)", _fetch_gee)
    else:
        log.info("SKIPPED: GEE Remote Sensing")

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("  PHASE 1 COLLECTION SUMMARY")
    log.info("=" * 60)
    successes = sum(1 for v in RESULTS.values() if v["status"] == "SUCCESS")
    failures  = sum(1 for v in RESULTS.values() if v["status"] == "FAILED")
    log.info("Completed: %d/%d steps succeeded.", successes, successes + failures)
    print(json.dumps(RESULTS, indent=2))
    return RESULTS


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UrbanCool AI — Phase 1 Data Collection")
    parser.add_argument("--skip-osm",     action="store_true", help="Skip OSM download")
    parser.add_argument("--skip-gee",     action="store_true", help="Skip GEE queries")
    parser.add_argument("--skip-weather", action="store_true", help="Skip weather fetch")
    args = parser.parse_args()

    results = run_all(
        skip_osm=args.skip_osm,
        skip_gee=args.skip_gee,
        skip_weather=args.skip_weather,
    )
    failed = [k for k, v in results.items() if v["status"] == "FAILED"]
    sys.exit(1 if failed else 0)
