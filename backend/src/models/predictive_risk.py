"""
UrbanCool AI — Phase 3: Short-Term Predictive Risk Model
backend/src/models/predictive_risk.py

Trains Scikit-Learn Random Forest and XGBoost regressors to predict daily ward-level
Land Surface Temperature (LST) based on:
  - Spatial features (road density, built-up ratio, vegetation deficit, albedo)
  - Meteorological features (daily max air temp, mean humidity, wind speed, solar radiation)

We simulate daily spatial-temporal LST using a biophysical model linking LST to regional
weather variations moderated by local surface properties (NDVI deficit and impervious cover).

Train-Test Split:
  - Train: Summers 2021 and 2022
  - Test: Summer 2023 (evaluates temporal generalisability)
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parents[2]
RAW_DIR       = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR     = BASE_DIR / "data" / "models"


def prepare_spatiotemporal_dataset() -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Combines daily weather statistics with static ward features to build
    the training and evaluation dataset.
    """
    # 1. Load static ward features
    features_path = PROCESSED_DIR / "features_wards.csv"
    if not features_path.exists():
        raise FileNotFoundError(f"Ward features not found: {features_path}. Run Phase 2 first.")
    df_wards = pd.read_csv(features_path)

    # 2. Load and process weather data (hourly -> daily)
    weather_path = RAW_DIR / "weather_ahmedabad.csv"
    if not weather_path.exists():
        raise FileNotFoundError(f"Weather data not found: {weather_path}. Run Phase 1 first.")
    df_weather = pd.read_csv(weather_path)

    # Extract date and group to daily metrics
    df_weather["date"] = pd.to_datetime(df_weather["date"])
    df_daily = df_weather.groupby("date").agg(
        temp_max           = ("temperature_2m", "max"),
        temp_mean          = ("temperature_2m", "mean"),
        humidity_mean      = ("relative_humidity_2m", "mean"),
        wind_mean          = ("wind_speed_10m", "mean"),
        apparent_temp_max  = ("apparent_temperature", "max"),
        apparent_temp_mean = ("apparent_temperature", "mean"),
        shortwave_max      = ("shortwave_radiation", "max"),
    ).reset_index()

    # Filter to summer months (March - June: 3, 4, 5, 6)
    df_daily = df_daily[df_daily["date"].dt.month.isin([3, 4, 5, 6])].copy()
    log.info("Loaded %d daily weather records across summers 2021-2023.", len(df_daily))

    # 3. Spatiotemporal Cross-Join (Wards x Days)
    df_wards["_key"] = 1
    df_daily["_key"] = 1
    st_df = pd.merge(df_wards, df_daily, on="_key").drop(columns=["_key"])

    # 4. Simulate Biophysical Target LST
    # Target LST is simulated based on base ward LST, weather apparent temp deviation,
    # and local vegetation cooling factors (higher NDVI -> less heating response).
    mean_apparent_temp = df_daily["apparent_temp_max"].mean()
    temp_dev = st_df["apparent_temp_max"] - mean_apparent_temp

    # Dynamic amplification: denser impervious zones heat up more on hot days
    veg_deficit = st_df["vegetation_deficit"]  # 1 - green_area_ratio
    heating_factor = 1.0 + (0.5 * veg_deficit)

    # Target daily LST
    st_df["target_lst"] = st_df["LST_mean"] + (temp_dev * heating_factor * 1.15)
    st_df["target_lst"] = st_df["target_lst"].round(2)

    # Define feature lists
    spatial_features = [
        "area_km2", "NDVI_mean", "NDBI_mean", "ALBEDO_mean",
        "road_density_km_km2", "road_coverage_ratio",
        "building_density_km2", "built_area_ratio",
        "green_area_ratio", "green_proximity_m",
        "water_area_ratio", "water_proximity_m",
        "impervious_proxy", "vegetation_deficit",
    ]

    weather_features = [
        "temp_max", "temp_mean", "humidity_mean", "wind_mean",
        "apparent_temp_max", "apparent_temp_mean", "shortwave_max",
    ]

    return st_df, spatial_features, weather_features


def train_predictive_models():
    """
    Train and evaluate Random Forest and XGBoost predictive models.
    """
    st_df, spatial_features, weather_features = prepare_spatiotemporal_dataset()
    features = spatial_features + weather_features

    # Temporal split: Train on 2021 & 2022, Test on 2023
    train_mask = st_df["date"].dt.year.isin([2021, 2022])
    test_mask  = st_df["date"].dt.year == 2023

    X_train = st_df.loc[train_mask, features]
    y_train = st_df.loc[train_mask, "target_lst"]
    X_test  = st_df.loc[test_mask, features]
    y_test  = st_df.loc[test_mask, "target_lst"]

    log.info("Dataset split:")
    log.info("  Train samples (2021-2022): %d", len(X_train))
    log.info("  Test samples (2023)     : %d", len(X_test))

    # ── 1. Scikit-Learn Random Forest ──────────────────────────────────────────
    log.info("Training Random Forest Regressor ...")
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)

    # ── 2. XGBoost Regressor ──────────────────────────────────────────────────
    log.info("Training XGBoost Regressor ...")
    xgb = XGBRegressor(n_estimators=100, learning_rate=0.08, max_depth=6, random_state=42, n_jobs=-1)
    xgb.fit(X_train, y_train)
    y_pred_xgb = xgb.predict(X_test)

    # ── Evaluation ────────────────────────────────────────────────────────────
    def eval_metrics(y_true, y_pred, name):
        mse  = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae  = mean_absolute_error(y_true, y_pred)
        r2   = r2_score(y_true, y_pred)
        log.info("%s Metrics (Test 2023):", name)
        log.info("  RMSE: %.4f°C", rmse)
        log.info("  MAE : %.4f°C", mae)
        log.info("  R²  : %.4f", r2)
        return {"rmse": rmse, "mae": mae, "r2": r2}

    rf_metrics = eval_metrics(y_test, y_pred_rf, "Random Forest")
    xgb_metrics = eval_metrics(y_test, y_pred_xgb, "XGBoost")

    # Save the best model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    best_model = rf if rf_metrics["r2"] > xgb_metrics["r2"] else xgb
    best_name  = "Random Forest" if rf_metrics["r2"] > xgb_metrics["r2"] else "XGBoost"

    model_path = MODEL_DIR / "predictive_risk_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": best_model,
            "features": features,
            "spatial_features": spatial_features,
            "weather_features": weather_features,
            "metrics": xgb_metrics if best_name == "XGBoost" else rf_metrics,
            "name": best_name
        }, f)

    log.info("Saved best model (%s) to %s", best_name, model_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    train_predictive_models()
