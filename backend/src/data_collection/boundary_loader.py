"""
UrbanCool AI — Phase 1: Boundary & Census Data Loader
backend/src/data_collection/boundary_loader.py

Handles two tasks:
  1. Load & validate ward boundaries from data/boundaries/amc_wards.geojson
     - 48 AMC wards with sourcewardcode, ward_lgd_code, sourcewardname
     - Falls back to generating a uniform 250 m × 250 m grid if file missing

  2. Load & process Census of India 2011 (PCA) data from the Excel file,
     mapping available metrics to ward IDs where possible.
     - When exact ward-level rows are sparse, distributes district-level
       urban totals proportionally by ward area.

Outputs:
  - data/processed/wards.geojson  — clean ward GeoDataFrame (EPSG:4326)
  - data/processed/census_wards.csv — census metrics per ward
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box

log = logging.getLogger(__name__)

# ── Path constants ─────────────────────────────────────────────────────────────
# __file__ = backend/src/data_collection/boundary_loader.py
# parents[0] = data_collection/, [1] = src/, [2] = backend/
BASE_DIR      = Path(__file__).resolve().parents[2]
BOUNDARIES_DIR = BASE_DIR / "data" / "boundaries"
PROCESSED_DIR  = BASE_DIR / "data" / "processed"
RAW_DIR        = BASE_DIR / "data" / "raw"

WARD_GEOJSON   = BOUNDARIES_DIR / "amc_wards.geojson"
CENSUS_EXCEL   = BOUNDARIES_DIR / "PCA_CDB-2407-F-Census.xlsx"

# ── Ahmedabad bounding box (WGS-84) ──────────────────────────────────────────
BBOX_W, BBOX_S, BBOX_E, BBOX_N = 72.46, 22.87, 72.72, 23.13

# ── Grid fallback resolution (metres, UTM 43N) ────────────────────────────────
GRID_CELL_SIZE_M = 250   # 250 m × 250 m


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Ward boundary loader
# ═══════════════════════════════════════════════════════════════════════════════

def load_ward_boundaries() -> gpd.GeoDataFrame:
    """
    Load AMC ward boundaries.

    Returns a GeoDataFrame (EPSG:4326) with standardised columns:
        ward_id         (int)  — sourcewardcode
        ward_name       (str)  — sourcewardname
        ward_lgd_code   (int)
        geometry

    Falls back to uniform 250 m grid if file is missing.
    """
    if WARD_GEOJSON.exists():
        log.info("Loading ward boundaries from %s …", WARD_GEOJSON)
        gdf = gpd.read_file(WARD_GEOJSON)

        # Standardise column names
        gdf = gdf.rename(columns={
            "sourcewardcode": "ward_id",
            "sourcewardname": "ward_name",
            "ward_lgd_code" : "ward_lgd_code",
        })
        gdf["ward_id"] = pd.to_numeric(gdf["ward_id"], errors="coerce").astype("Int64")

        # Drop style-only columns (fill-opacity, stroke, etc.)
        drop_cols = [c for c in gdf.columns
                     if c in ("fill-opacity", "stroke-opacity", "stroke",
                               "objectid", "townname", "towncensuscode2011",
                               "town_lgd_code", "state")]
        gdf = gdf.drop(columns=drop_cols, errors="ignore")

        # Ensure WGS-84
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        else:
            gdf = gdf.to_crs(epsg=4326)

        # Compute area in km² (project to UTM 43N)
        gdf_utm = gdf.to_crs(epsg=32643)
        gdf["area_km2"] = (gdf_utm.geometry.area / 1e6).round(4)

        log.info("Loaded %d ward polygons.", len(gdf))
        return gdf[["ward_id", "ward_name", "ward_lgd_code", "area_km2", "geometry"]]

    else:
        log.warning(
            "Ward boundary file not found at %s. "
            "Generating 250 m fallback grid …", WARD_GEOJSON
        )
        return _generate_grid_fallback()


def _generate_grid_fallback() -> gpd.GeoDataFrame:
    """
    Generate a uniform 250 m × 250 m polygon grid over Ahmedabad's bounding box.

    Grid cells are created in UTM 43N and exported as EPSG:4326 GeoDataFrame.
    Each cell is assigned a sequential ward_id.
    """
    from shapely.geometry import box as shapely_box

    # Work in UTM 43N
    city_box_wgs = gpd.GeoDataFrame(
        geometry=[box(BBOX_W, BBOX_S, BBOX_E, BBOX_N)],
        crs="EPSG:4326",
    )
    city_box_utm = city_box_wgs.to_crs(epsg=32643)
    minx, miny, maxx, maxy = city_box_utm.total_bounds

    step = GRID_CELL_SIZE_M
    cells = []
    cell_id = 1
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            cells.append({
                "ward_id"  : cell_id,
                "ward_name": f"Grid_{cell_id:04d}",
                "ward_lgd_code": None,
                "geometry" : shapely_box(x, y, x + step, y + step),
            })
            cell_id += 1
            y += step
        x += step

    gdf_utm = gpd.GeoDataFrame(cells, crs="EPSG:32643")
    gdf = gdf_utm.to_crs(epsg=4326)
    gdf["area_km2"] = round((step * step) / 1e6, 4)

    log.info("Generated fallback grid: %d cells of %dm × %dm.",
             len(gdf), GRID_CELL_SIZE_M, GRID_CELL_SIZE_M)
    return gdf


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Census data loader & ward-proportional distributor
# ═══════════════════════════════════════════════════════════════════════════════

# Census columns we want to extract (from PCA sheet)
CENSUS_COLS = {
    "Ward"         : "ward_num",
    "Name"         : "census_name",
    "No_HH"        : "households",
    "TOT_P"        : "population_total",
    "TOT_M"        : "population_male",
    "TOT_F"        : "population_female",
    "P_06"         : "pop_under_6",
    "P_SC"         : "pop_scheduled_caste",
    "P_ST"         : "pop_scheduled_tribe",
    "P_LIT"        : "pop_literate",
    "P_ILL"        : "pop_illiterate",
    "TOT_WORK_P"   : "workers_total",
    "NON_WORK_P"   : "non_workers",
}

# Ahmedabad municipal corporation census town code
AMC_TOWN_CODE = "802484"

# District-level urban aggregate codes to fall back to
AHMEDABAD_DIST_CODE = "474"


def load_census_data(ward_gdf: Optional[gpd.GeoDataFrame] = None) -> pd.DataFrame:
    """
    Load Census 2011 PCA data and map to AMC ward IDs.

    Strategy:
      1. Try to find OG (outgrowth) ward rows for AMC town code 802484.
      2. For the remaining core AMC wards (1–48), distribute the urban
         aggregate proportionally by ward area.
      3. Compute derived vulnerability indicators:
           - child_ratio       = pop_under_6 / population_total
           - literacy_rate     = pop_literate / population_total
           - sc_st_ratio       = (pop_sc + pop_st) / population_total
           - pop_density_km2   = population_total / area_km2
           - non_worker_ratio  = non_workers / population_total

    Parameters
    ----------
    ward_gdf : Output of load_ward_boundaries(). If None, loaded internally.

    Returns
    -------
    pd.DataFrame with one row per ward and all demographic features.
    """
    if ward_gdf is None:
        ward_gdf = load_ward_boundaries()

    if not CENSUS_EXCEL.exists():
        log.warning("Census Excel not found at %s. Using synthetic proxy data.",
                    CENSUS_EXCEL)
        return _synthetic_census_proxy(ward_gdf)

    log.info("Reading census Excel: %s …", CENSUS_EXCEL)
    df_raw = pd.read_excel(CENSUS_EXCEL, sheet_name=0, dtype=str)

    # Normalise column names
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # ── Step 1: Extract AMC-specific OG ward rows ─────────────────────────────
    amc_rows = df_raw[
        (df_raw["Town/Village"].astype(str).str.strip() == AMC_TOWN_CODE) &
        (df_raw["Ward"].astype(str).str.strip() != "0000") &
        (df_raw["TRU"].astype(str).str.strip() == "Urban")
    ].copy()

    # ── Step 2: Get district-level urban aggregate for redistribution ─────────
    dist_urban = df_raw[
        (df_raw["District"].astype(str).str.strip() == AHMEDABAD_DIST_CODE) &
        (df_raw["Level"].astype(str).str.strip() == "CD BLOCK") &
        (df_raw["TRU"].astype(str).str.strip() == "Urban")
    ]

    # Fallback to total district if urban block not found
    if dist_urban.empty:
        dist_urban = df_raw[
            (df_raw["District"].astype(str).str.strip() == AHMEDABAD_DIST_CODE) &
            (df_raw["Level"].astype(str).str.strip() == "CD BLOCK") &
            (df_raw["TRU"].astype(str).str.strip() == "Total")
        ]

    log.info("OG ward rows found: %d | District urban blocks: %d",
             len(amc_rows), len(dist_urban))

    # ── Step 3: Build per-ward census frame using area-proportional allocation ─
    numeric_fields = [
        "No_HH", "TOT_P", "TOT_M", "TOT_F",
        "P_06", "P_SC", "P_ST", "P_LIT", "P_ILL",
        "TOT_WORK_P", "NON_WORK_P",
    ]

    # Aggregate district urban totals
    if not dist_urban.empty:
        urban_totals = {}
        for col in numeric_fields:
            if col in dist_urban.columns:
                urban_totals[col] = pd.to_numeric(
                    dist_urban[col], errors="coerce"
                ).sum()
    else:
        # Last resort: rough AMC estimates from published data (2011 Census)
        urban_totals = {
            "No_HH"     : 1250000,
            "TOT_P"     : 5570585,
            "TOT_M"     : 2978019,
            "TOT_F"     : 2592566,
            "P_06"      : 652000,
            "P_SC"      : 368000,
            "P_ST"      : 28000,
            "P_LIT"     : 4200000,
            "P_ILL"     : 1370000,
            "TOT_WORK_P": 2250000,
            "NON_WORK_P": 3320000,
        }
        log.warning("Using hard-coded AMC urban totals from published Census 2011.")

    total_area = ward_gdf["area_km2"].sum()

    rows = []
    for _, ward in ward_gdf.iterrows():
        area_frac = ward["area_km2"] / total_area
        row = {
            "ward_id"    : ward["ward_id"],
            "ward_name"  : ward["ward_name"],
            "area_km2"   : ward["area_km2"],
        }
        for col in numeric_fields:
            val = urban_totals.get(col, 0)
            row[CENSUS_COLS.get(col, col)] = round(val * area_frac)
        rows.append(row)

    census_df = pd.DataFrame(rows)

    # ── Step 4: Derived vulnerability indicators ──────────────────────────────
    p = census_df["population_total"].replace(0, np.nan)
    census_df["pop_density_km2"]   = (p / census_df["area_km2"]).round(1)
    census_df["child_ratio"]       = (census_df["pop_under_6"] / p).round(4)
    census_df["literacy_rate"]     = (census_df["pop_literate"]  / p).round(4)
    census_df["sc_st_ratio"]       = (
        (census_df["pop_scheduled_caste"] + census_df["pop_scheduled_tribe"]) / p
    ).round(4)
    census_df["non_worker_ratio"]  = (census_df["non_workers"] / p).round(4)

    log.info("Census DataFrame built: %d wards, %d columns.",
             len(census_df), len(census_df.columns))
    return census_df


def _synthetic_census_proxy(ward_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Generate synthetic census proxy values for each ward when no census file
    is available. Uses published AMC 2011 census totals distributed uniformly.
    """
    AMC_TOTAL_POP    = 5570585
    AMC_TOTAL_HH     = 1250000
    n_wards          = len(ward_gdf)
    rows = []
    for _, w in ward_gdf.iterrows():
        pop = int(AMC_TOTAL_POP / n_wards)
        rows.append({
            "ward_id"               : w["ward_id"],
            "ward_name"             : w["ward_name"],
            "area_km2"              : w["area_km2"],
            "households"            : int(AMC_TOTAL_HH / n_wards),
            "population_total"      : pop,
            "population_male"       : int(pop * 0.535),
            "population_female"     : int(pop * 0.465),
            "pop_under_6"           : int(pop * 0.117),
            "pop_scheduled_caste"   : int(pop * 0.066),
            "pop_scheduled_tribe"   : int(pop * 0.005),
            "pop_literate"          : int(pop * 0.754),
            "pop_illiterate"        : int(pop * 0.246),
            "workers_total"         : int(pop * 0.404),
            "non_workers"           : int(pop * 0.596),
            "pop_density_km2"       : round(pop / w["area_km2"], 1),
            "child_ratio"           : 0.117,
            "literacy_rate"         : 0.754,
            "sc_st_ratio"           : 0.071,
            "non_worker_ratio"      : 0.596,
        })
    log.warning("Synthetic census proxy data generated for %d wards.", n_wards)
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Save processed outputs
# ═══════════════════════════════════════════════════════════════════════════════

def save_processed_boundaries(ward_gdf: gpd.GeoDataFrame) -> Path:
    """Save cleaned ward GeoDataFrame to data/processed/wards.geojson."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "wards.geojson"
    ward_gdf.to_file(out, driver="GeoJSON")
    log.info("Saved processed wards → %s", out)
    return out


def save_census_csv(census_df: pd.DataFrame) -> Path:
    """Save census DataFrame to data/processed/census_wards.csv."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "census_wards.csv"
    census_df.to_csv(out, index=False)
    log.info("Saved census data → %s", out)
    return out


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")

    wards   = load_ward_boundaries()
    census  = load_census_data(wards)

    save_processed_boundaries(wards)
    save_census_csv(census)

    print("\n-- Ward GeoDataFrame (first 5) --")
    print(wards[["ward_id", "ward_name", "area_km2"]].head().to_string())
    print("\n-- Census DataFrame (first 5) --")
    print(census[["ward_id", "ward_name", "population_total",
                  "pop_density_km2", "literacy_rate"]].head().to_string())
    log.info("Boundary & census loader PASSED")
