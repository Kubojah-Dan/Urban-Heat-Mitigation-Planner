"""
UrbanCool AI — Phase 3: Hotspot & Heat Vulnerability Index (HVI) Calculator
backend/src/models/hvi_model.py

Computes three sub-indices to calculate the Heat Vulnerability Index (HVI):
  1. Exposure Index (LST and Landsat p90 LST)
  2. Sensitivity Index (pop density, child ratio, sc/st ratio, non-workers, illiteracy)
  3. Adaptive Capacity Index (NDVI, Albedo, green space coverage and proximity, water proximity)

HVI is calculated as:
  HVI = (Exposure + Sensitivity + (1 - Adaptive Capacity)) / 3.0

Wards are ranked and classified into four vulnerability categories:
  - Extreme (HVI >= 0.75 or top 15%)
  - High (0.50 <= HVI < 0.75)
  - Moderate (0.25 <= HVI < 0.50)
  - Low (HVI < 0.25)
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def calculate_hvi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Exposure, Sensitivity, Adaptive Capacity, and HVI.
    """
    df = df.copy()

    # ── 1. Exposure Index (EI) ────────────────────────────────────────────────
    # Weights: 60% LST p90 (extreme peaks), 40% LST mean (general baseline)
    lst_mean_norm = df.get("LST_mean_norm", df["LST_mean"] / df["LST_mean"].max())
    lst_p90_norm  = df.get("LST_p90_norm", df["LST_p90"] / df["LST_p90"].max())
    df["exposure_index"] = (0.6 * lst_p90_norm + 0.4 * lst_mean_norm).round(4)

    # ── 2. Sensitivity Index (SI) ─────────────────────────────────────────────
    # Weights: 25% pop density, 20% child ratio, 20% SC/ST ratio, 20% non-worker, 15% illiteracy
    pop_density_norm = df.get("pop_density_km2_norm", pd.Series(0.5, index=df.index))
    child_ratio_norm = df.get("child_ratio_norm", pd.Series(0.5, index=df.index))
    sc_st_norm       = df.get("sc_st_ratio_norm", pd.Series(0.5, index=df.index))
    non_worker_norm  = df.get("non_worker_ratio_norm", pd.Series(0.5, index=df.index))
    # Literacy is protective, so illiteracy = 1 - literacy
    literacy_val     = df.get("literacy_rate", pd.Series(0.75, index=df.index))
    illiteracy_val   = 1 - literacy_val

    df["sensitivity_index"] = (
        0.25 * pop_density_norm +
        0.20 * child_ratio_norm +
        0.20 * sc_st_norm +
        0.20 * non_worker_norm +
        0.15 * illiteracy_val
    ).round(4)

    # ── 3. Adaptive Capacity Index (ACI) ──────────────────────────────────────
    # Weights: 30% NDVI, 15% Albedo, 25% green area ratio, 15% green prox (closer is better), 15% water prox (closer is better)
    ndvi_norm       = df.get("NDVI_mean_norm", pd.Series(0.5, index=df.index))
    albedo_norm     = df.get("ALBEDO_mean_norm", pd.Series(0.5, index=df.index))
    green_ratio     = df.get("green_area_ratio_norm", pd.Series(0.0, index=df.index))
    # Proximities: lower distance means higher capacity, so use 1 - distance_norm
    green_prox_norm = df.get("green_proximity_m_norm", pd.Series(1.0, index=df.index))
    water_prox_norm = df.get("water_proximity_m_norm", pd.Series(1.0, index=df.index))

    df["adaptive_capacity_index"] = (
        0.30 * ndvi_norm +
        0.15 * albedo_norm +
        0.25 * green_ratio +
        0.15 * (1 - green_prox_norm) +
        0.15 * (1 - water_prox_norm)
    ).round(4)

    # ── 4. Heat Vulnerability Index (HVI) ─────────────────────────────────────
    # HVI = average of Exposure, Sensitivity, and Lack of Adaptive Capacity
    df["hvi"] = ((df["exposure_index"] + df["sensitivity_index"] + (1 - df["adaptive_capacity_index"])) / 3.0).round(4)

    # ── 5. Ranking and Classification ──────────────────────────────────────────
    df["hvi_rank"] = df["hvi"].rank(ascending=False, method="min").astype(int)
    df["lst_rank"] = df["LST_mean"].rank(ascending=False, method="min").astype(int)

    # Classify HVI into tiers
    # We use dynamic quantiles for better spread across the 48 wards
    q75 = df["hvi"].quantile(0.75)
    q50 = df["hvi"].quantile(0.50)
    q25 = df["hvi"].quantile(0.25)

    def classify_vulnerability(hvi_val):
        if hvi_val >= q75:
            return "Extreme"
        elif hvi_val >= q50:
            return "High"
        elif hvi_val >= q25:
            return "Moderate"
        else:
            return "Low"

    df["vulnerability_class"] = df["hvi"].apply(classify_vulnerability)

    return df


def update_processed_datasets() -> pd.DataFrame:
    """
    Load features_wards.csv, calculate HVI, and save the updated
    CSV and GeoJSON back to processed/.
    """
    csv_path = PROCESSED_DIR / "features_wards.csv"
    geojson_path = PROCESSED_DIR / "features_wards.geojson"

    if not csv_path.exists():
        raise FileNotFoundError(f"Features table not found at {csv_path}. Run Phase 2 first.")

    log.info("Calculating HVI indices from %s ...", csv_path)
    df = pd.read_csv(csv_path)
    df_hvi = calculate_hvi(df)

    # Save CSV
    df_hvi.to_csv(csv_path, index=False)
    log.info("Saved updated HVI features CSV -> %s", csv_path)

    # Save GeoJSON
    if geojson_path.exists():
        wards_gdf = gpd.read_file(geojson_path)
        # Drop columns that we will re-merge to prevent duplicates
        keep_cols = ["ward_id", "geometry"]
        wards_base = wards_gdf[keep_cols].copy()
        updated_gdf = wards_base.merge(df_hvi, on="ward_id", how="inner")
        updated_gdf.to_file(geojson_path, driver="GeoJSON")
        log.info("Saved updated HVI features GeoJSON -> %s", geojson_path)

    return df_hvi


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    df = update_processed_datasets()
    print("\n" + "=" * 80)
    print("TOP 10 WARD HOTSPOTS BY HVI RANK")
    print("=" * 80)
    print(df.sort_values(by="hvi_rank")[["hvi_rank", "ward_id", "ward_name", "hvi", "exposure_index", "sensitivity_index", "adaptive_capacity_index", "vulnerability_class"]].head(10).to_string(index=False))
