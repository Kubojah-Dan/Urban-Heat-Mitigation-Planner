"""
UrbanCool AI — Phase 1: Open-Meteo Historical Weather Collector
backend/src/data_collection/weather_collector.py

Fetches historical hourly weather from the Open-Meteo Archive API
(https://open-meteo.com/en/docs/historical-weather-api) for Ahmedabad.

Variables collected:
  - temperature_2m            (°C)
  - relative_humidity_2m      (%)
  - wind_speed_10m            (km/h)
  - apparent_temperature      (°C)  — feels-like / heat-index proxy
  - precipitation             (mm)
  - surface_pressure          (hPa)
  - shortwave_radiation       (W/m²) — incoming solar proxy
  - et0_fao_evapotranspiration (mm)  — drought/aridity proxy

Time window: March–June for study years 2021, 2022, 2023.
Location: Ahmedabad city centre (23.0225°N, 72.5714°E).

Output: CSV saved to data/raw/weather_ahmedabad.csv
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
OPEN_METEO_URL   = "https://archive-api.open-meteo.com/v1/archive"
AHMEDABAD_LAT    = 23.0225
AHMEDABAD_LON    = 72.5714
STUDY_YEARS      = [2021, 2022, 2023]
SUMMER_START_MM  = "03-01"
SUMMER_END_MM    = "06-30"
RETRY_DELAY_SEC  = 5
MAX_RETRIES      = 3

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "apparent_temperature",
    "precipitation",
    "surface_pressure",
    "shortwave_radiation",
    "et0_fao_evapotranspiration",
]


def _fetch_one_season(year: int) -> pd.DataFrame:
    """
    Fetch a single summer season (March–June) for the given year.

    Returns a DataFrame with a DatetimeIndex and one column per variable.
    """
    params = {
        "latitude"        : AHMEDABAD_LAT,
        "longitude"       : AHMEDABAD_LON,
        "start_date"      : f"{year}-{SUMMER_START_MM}",
        "end_date"        : f"{year}-{SUMMER_END_MM}",
        "hourly"          : ",".join(HOURLY_VARIABLES),
        "timezone"        : "Asia/Kolkata",
        "wind_speed_unit" : "kmh",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("Fetching weather: year=%d (attempt %d/%d) …",
                     year, attempt, MAX_RETRIES)
            resp = requests.get(OPEN_METEO_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, ValueError) as exc:
            log.warning("Attempt %d failed: %s", attempt, exc)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY_SEC)

    hourly = data.get("hourly", {})
    if not hourly:
        raise ValueError(f"Empty 'hourly' block in Open-Meteo response for {year}.")

    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df["year"] = year
    log.info("Fetched %d hourly records for %d.", len(df), year)
    return df


def fetch_weather(
    years: list[int] = STUDY_YEARS,
    save: bool = True,
) -> pd.DataFrame:
    """
    Fetch historical hourly weather for all study years and concatenate.

    Parameters
    ----------
    years : List of years to fetch.
    save  : If True, write CSV to data/raw/weather_ahmedabad.csv.

    Returns
    -------
    pd.DataFrame — one row per hour, all years stacked vertically.
    """
    frames = []
    for yr in years:
        df = _fetch_one_season(yr)
        frames.append(df)

    combined = pd.concat(frames).sort_index()

    # Derived: daily mean temp aggregation (useful for Phase 2 merge)
    combined["date"] = combined.index.date

    log.info("Total hourly records fetched: %d (%d years).",
             len(combined), len(years))

    if save:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        out = RAW_DIR / "weather_ahmedabad.csv"
        combined.reset_index().to_csv(out, index=False)
        log.info("Weather data saved → %s", out)

    return combined


def compute_daily_weather_summary(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Aggregate hourly weather to daily statistics for Phase 2 feature merging.

    If df is None, loads from data/raw/weather_ahmedabad.csv.

    Returns
    -------
    pd.DataFrame with columns:
        date, temp_mean, temp_max, temp_min,
        rh_mean, wind_mean, precip_sum,
        solar_rad_mean, apparent_temp_max
    """
    if df is None:
        csv_path = RAW_DIR / "weather_ahmedabad.csv"
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Weather CSV not found at {csv_path}. "
                "Run fetch_weather() first."
            )
        df = pd.read_csv(csv_path, parse_dates=["time"])
        df = df.set_index("time")

    daily = df.groupby("date").agg(
        temp_mean       = ("temperature_2m",           "mean"),
        temp_max        = ("temperature_2m",            "max"),
        temp_min        = ("temperature_2m",            "min"),
        rh_mean         = ("relative_humidity_2m",     "mean"),
        wind_mean       = ("wind_speed_10m",            "mean"),
        precip_sum      = ("precipitation",             "sum"),
        solar_rad_mean  = ("shortwave_radiation",       "mean"),
        apparent_temp_max = ("apparent_temperature",    "max"),
        et0_mean        = ("et0_fao_evapotranspiration","mean"),
    ).reset_index()

    daily["date"] = pd.to_datetime(daily["date"])
    log.info("Daily weather summary: %d days.", len(daily))
    return daily


def get_summer_heat_stats(df: Optional[pd.DataFrame] = None) -> dict:
    """
    Compute summary heat statistics across all study summers.

    Returns dict with keys: avg_max_temp, hottest_day, mean_humidity,
    mean_apparent_temp, total_precip.
    """
    daily = compute_daily_weather_summary(df)
    stats = {
        "avg_max_temp_C"      : round(daily["temp_max"].mean(), 2),
        "hottest_day"         : str(daily.loc[daily["temp_max"].idxmax(), "date"].date()),
        "hottest_temp_C"      : round(daily["temp_max"].max(), 2),
        "mean_humidity_pct"   : round(daily["rh_mean"].mean(), 2),
        "mean_apparent_temp_C": round(daily["apparent_temp_max"].mean(), 2),
        "total_precip_mm"     : round(daily["precip_sum"].sum(), 2),
        "mean_solar_W_m2"     : round(daily["solar_rad_mean"].mean(), 2),
    }
    return stats


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")
    df = fetch_weather()
    stats = get_summer_heat_stats(df)
    import json
    print(json.dumps(stats, indent=2))
    log.info("Weather collector PASSED ✅")
