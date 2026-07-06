"""
UrbanCool AI — Phase 5: FastAPI Backend Server
backend/src/api/main.py

Exposes REST API endpoints for React integration:
  - GET /api/city-summary  : Aggregated municipal statistics.
  - GET /api/wards         : Enriched ward boundary GeoJSON.
  - GET /api/wards/{id}    : Detailed metrics and top 3 interventions.
  - GET /api/predict       : Dynamic XGBoost-based heat risk forecast.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("api_main")

app = FastAPI(
    title="UrbanCool AI API",
    description="Satellite-driven urban heat mitigation planner API",
    version="1.0.0"
)

# Enable CORS for React integration (default Vite port: 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths & Data Loading ──────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR     = BASE_DIR / "data" / "models"

# Cache loaded datasets in-memory
FEATURES_CSV = PROCESSED_DIR / "features_wards.csv"
FEATURES_GEO = PROCESSED_DIR / "features_wards.geojson"
MODEL_PKL    = MODEL_DIR / "predictive_risk_model.pkl"

df_wards: pd.DataFrame | None = None
gdf_wards: gpd.GeoDataFrame | None = None
model_data: dict[str, Any] | None = None


def load_assets():
    global df_wards, gdf_wards, model_data
    if FEATURES_CSV.exists():
        df_wards = pd.read_csv(FEATURES_CSV)
        log.info("Loaded CSV: %d wards.", len(df_wards))
    else:
        log.error("CSV features table missing at %s", FEATURES_CSV)

    if FEATURES_GEO.exists():
        gdf_wards = gpd.read_file(FEATURES_GEO)
        log.info("Loaded GeoJSON: %d features.", len(gdf_wards))
    else:
        log.error("GeoJSON boundaries missing at %s", FEATURES_GEO)

    if MODEL_PKL.exists():
        with open(MODEL_PKL, "rb") as f:
            model_data = pickle.load(f)
        log.info("Loaded XGBoost ML model from %s", MODEL_PKL)
    else:
        log.error("Model binary missing at %s", MODEL_PKL)


@app.on_event("startup")
def startup_event():
    load_assets()


# ── Helper functions ──────────────────────────────────────────────────────────
from src.recommender.engine import get_recommendations_for_ward


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/city-summary")
def get_city_summary():
    """Return city-level aggregated stats."""
    if df_wards is None:
        raise HTTPException(status_code=500, detail="Data assets not loaded.")

    total_pop = int(df_wards["population_total"].sum())
    avg_lst   = float(df_wards["LST_mean"].mean())
    max_lst   = float(df_wards["LST_mean"].max())
    avg_hvi   = float(df_wards["hvi"].mean())

    # Count of wards in each vulnerability class
    vclass_counts = df_wards["vulnerability_class"].value_counts().to_dict()

    # Total green area (m2) and built area (m2)
    total_green_m2 = float(df_wards["green_area_m2"].sum())
    total_built_m2 = float(df_wards["built_area_m2"].sum())
    total_area_km2 = float(df_wards["area_km2"].sum())

    city_green_ratio = total_green_m2 / (total_area_km2 * 1e6)
    city_built_ratio = total_built_m2 / (total_area_km2 * 1e6)

    return {
        "city_name": "Ahmedabad, India",
        "total_population": total_pop,
        "avg_lst_mean": round(avg_lst, 2),
        "max_lst_mean": round(max_lst, 2),
        "avg_hvi": round(avg_hvi, 3),
        "vulnerability_counts": vclass_counts,
        "city_green_ratio": round(city_green_ratio, 4),
        "city_built_ratio": round(city_built_ratio, 4),
        "total_area_km2": round(total_area_km2, 2)
    }


@app.get("/api/wards")
def get_wards():
    """Return GeoJSON boundary data injected with HVI and top recommendation summary."""
    if gdf_wards is None or df_wards is None:
        raise HTTPException(status_code=500, detail="Spatial datasets not loaded.")

    # Convert to standard python dict representation
    geojson = gdf_wards.to_json()
    parsed = gpd.read_file(geojson)

    # For each feature, let's inject the primary recommendation to show on map hover
    recs_map = {}
    for wid in df_wards["ward_id"]:
        try:
            recs = get_recommendations_for_ward(int(wid), df_wards)
            if recs:
                recs_map[wid] = {
                    "rec_title": recs[0]["title"],
                    "rec_score": recs[0]["priority_score"],
                    "rec_key": recs[0]["key"],
                }
        except Exception:
            pass

    # Inject properties
    def add_rec_properties(row):
        wid = int(row["ward_id"])
        if wid in recs_map:
            row["primary_rec_title"] = recs_map[wid]["rec_title"]
            row["primary_rec_score"] = recs_map[wid]["rec_score"]
            row["primary_rec_key"] = recs_map[wid]["rec_key"]
        return row

    parsed = parsed.apply(add_rec_properties, axis=1)
    return json_parse(parsed.to_json())


@app.get("/api/wards/{id}")
def get_ward_detail(id: int):
    """Return detailed metrics and recommendations for a single ward."""
    if df_wards is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")

    ward_rows = df_wards[df_wards["ward_id"] == id]
    if ward_rows.empty:
        raise HTTPException(status_code=404, detail=f"Ward ID {id} not found.")

    ward = ward_rows.iloc[0].to_dict()

    # Re-cast float types to avoid JSON serialization errors
    for k, v in ward.items():
        if isinstance(v, (np.integer, np.int64)):
            ward[k] = int(v)
        elif isinstance(v, (np.floating, np.float64)):
            ward[k] = float(v)

    # Get interventions
    try:
        recommendations = get_recommendations_for_ward(id, df_wards)
    except Exception as exc:
        log.error("Failed to generate recommendations: %s", exc)
        recommendations = []

    return {
        "ward_metrics": ward,
        "recommendations": recommendations
    }


@app.get("/api/predict")
def get_heat_prediction(
    temp: float = Query(38.0, description="Ambient air temperature in Celsius (°C)"),
    humidity: float = Query(45.0, description="Relative humidity percentage (%)"),
):
    """
    Run XGBoost inference using user-provided weather inputs to predict LST
    for each ward dynamically.
    """
    if df_wards is None or model_data is None:
        raise HTTPException(status_code=500, detail="Model assets not loaded.")

    model = model_data["model"]
    features = model_data["features"]
    spatial_features = model_data["spatial_features"]

    # Compute daily apparent temperature using standard formula (approximate)
    # AT = T + 0.33 * e - 0.70 * ws - 4.0 (we estimate e: water vapor pressure from humidity)
    e = (humidity / 100.0) * 6.105 * np.exp((17.27 * temp) / (237.7 + temp))
    apparent_temp = temp + 0.33 * e - 4.0

    # Build inference rows for all 48 wards
    rows = []
    ward_ids = []
    for _, ward in df_wards.iterrows():
        row = {}
        for sf in spatial_features:
            row[sf] = ward[sf]

        # Add meteorological features
        row["temp_max"]           = temp
        row["temp_mean"]          = temp - 4.0  # approximate mean
        row["humidity_mean"]      = humidity
        row["wind_mean"]          = 8.0          # default moderate wind speed
        row["apparent_temp_max"]  = apparent_temp
        row["apparent_temp_mean"] = apparent_temp - 3.0
        row["shortwave_max"]      = 750.0        # standard sunny summer day

        rows.append(row)
        ward_ids.append(int(ward["ward_id"]))

    df_inf = pd.DataFrame(rows)[features]
    preds = model.predict(df_inf)

    # Format output as a mapping: ward_id -> predicted LST
    predictions = {}
    for wid, pred in zip(ward_ids, preds):
        predictions[wid] = round(float(pred), 2)

    return {
        "input_weather": {
            "temperature_C": temp,
            "humidity_pct": humidity,
            "calculated_apparent_temp_C": round(apparent_temp, 2)
        },
        "predictions": predictions
    }


# ── Added: Simulation Sandbox & Chatbot Endpoints ──────────────────────────────
from pydantic import BaseModel

class SimulationParams(BaseModel):
    wardId: str
    cityName: str
    wardName: str
    baseLst: float
    baseCanopy: float
    baseHvi: float
    popDensity: float
    addedCanopy: float
    addedCoolRoofs: float

@app.post("/api/simulation")
def run_sandbox_simulation(params: SimulationParams):
    """
    Run custom what-if simulation for a ward.
    Computes ambient temperature drop and HVI score reduction.
    """
    if df_wards is None:
        raise HTTPException(status_code=500, detail="Datasets not loaded.")

    # Convert wardId to int if it is a digit
    wid = int(params.wardId) if params.wardId.isdigit() else None
    
    # Calculate drops: 1% canopy = 0.22°C drop. 1% cool roofs = 0.12°C drop (matching UI sandbox formulas)
    canopy_drop = params.addedCanopy * 0.22
    cool_roofs_drop = params.addedCoolRoofs * 0.12
    temp_drop = round(canopy_drop + cool_roofs_drop, 2)
    new_lst = round(max(20.0, params.baseLst - temp_drop), 2)

    # Calculate HVI reduction: 1% canopy = -0.15 HVI, 1% cool roofs = -0.05 HVI
    hvi_reduction = (params.addedCanopy * 0.15) + (params.addedCoolRoofs * 0.05)
    new_hvi = round(max(0.05, params.baseHvi - hvi_reduction), 2)

    # Fetch recommendations
    recommendations = []
    if wid is not None:
        try:
            recs = get_recommendations_for_ward(wid, df_wards)
            recommendations = [f"{r['title']}: {r['rationale']}" for r in recs]
        except Exception:
            pass

    if not recommendations:
        recommendations = [
            f"Plant drought-resilient shade tree species (e.g., Neem, Karanj) in {params.wardName} to increase canopy cover by {params.addedCanopy}%.",
            f"Apply high-solar reflectance coatings (SRI >= 104) on flat rooftops in {params.wardName} to retro-fit {params.addedCoolRoofs}% of structures.",
            "Install cooling bioswales and permeable pavements along high-traffic corridors."
        ]

    explanation = (
        f"Simulated retrofitting of {params.addedCoolRoofs}% cool roof surfaces and +{params.addedCanopy}% "
        f"canopy expansion in {params.wardName} reduces localized solar sensible heat storing. "
        f"This yields a calculated thermal drop of -{temp_drop}°C, lowering overall risk class from HVI {params.baseHvi} to {new_hvi}."
    )

    import datetime
    return {
        "wardId": params.wardId,
        "wardName": params.wardName,
        "cityName": params.cityName,
        "originalLst": params.baseLst,
        "newLst": new_lst,
        "originalHvi": params.baseHvi,
        "newHvi": new_hvi,
        "originalCanopy": params.baseCanopy,
        "newCanopy": params.baseCanopy + params.addedCanopy,
        "originalCoolRoofs": 0,
        "newCoolRoofs": params.addedCoolRoofs,
        "temperatureDrop": temp_drop,
        "aiExplanation": explanation,
        "recommendations": recommendations[:3],
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
    }

class ChatParams(BaseModel):
    message: str
    history: list[dict[str, str]]

@app.post("/api/chat")
def chat_with_advisor(params: ChatParams):
    """
    Expert AI Eco-Planning Advisor.
    Uses in-memory datasets to answer detailed queries about Ahmedabad's heat risk.
    """
    if df_wards is None:
        raise HTTPException(status_code=500, detail="Datasets not loaded.")

    msg = params.message.lower()
    
    # 1. Search if the user mentioned a specific ward name
    matched_ward = None
    for _, row in df_wards.iterrows():
        wname = str(row["ward_name"]).lower()
        if wname in msg:
            matched_ward = row
            break

    if matched_ward is not None:
        wid = int(matched_ward["ward_id"])
        wname = matched_ward["ward_name"]
        lst = float(matched_ward["LST_mean"])
        hvi = float(matched_ward["hvi"])
        pop_density = float(matched_ward["pop_density_km2"])
        canopy = float(matched_ward["NDVI_mean"]) * 100 # approximate percent
        vclass = matched_ward["vulnerability_class"]
        
        # Get recommedations
        recs = []
        try:
            recs = get_recommendations_for_ward(wid, df_wards)
        except Exception:
            pass
        
        recs_str = "\n".join([f"- **{r['title']}** (Priority: {r['priority_score']}%)\n  *Rationale:* {r['rationale']}" for r in recs[:3]])
        
        response = (
            f"Here is the ecological analysis for **{wname}** (Ward ID: {wid}):\n\n"
            f"- **Heat Class**: {vclass} (Mean LST: **{lst:.1f}°C**)\n"
            f"- **Risk Level**: **{hvi:.2f}/10 HVI**\n"
            f"- **Population Density**: **{pop_density:.0f}/km²**\n"
            f"- **Vegetation Density (NDVI)**: **{canopy:.1f}%**\n\n"
            f"### Prioritized Mitigation Path:\n{recs_str}\n\n"
            f"Would you like me to simulate a What-If scenario (e.g. +10% canopy) on {wname}?"
        )
        return {"text": response}

    # 2. Heuristics for cooling strategies
    if "cool roof" in msg or "albedo" in msg or "reflective" in msg:
        response = (
            "### Cool Roof Technology (Albedo Retrofits)\n\n"
            "Applying high-albedo coatings (solar reflectance index SRI >= 104) on flat rooftops is highly cost-effective.\n\n"
            "- **Cooling rate**: Each 10% increase in cool roof surfaces lowers local LST by approximately **1.2°C**.\n"
            "- **Target zones**: High-density residential pockets with tin or concrete roofs (e.g., *Maninagar*, *Bapu Nagar*).\n"
            "- **Advantage**: Instantaneous sensible heat reduction; reduces indoor ambient temperatures by 2-4°C."
        )
        return {"text": response}

    if "canopy" in msg or "forest" in msg or "tree" in msg or "plant" in msg:
        response = (
            "### Urban Forestry & Tree Canopies\n\n"
            "Planting native shade-providing species acts as a biophysical buffer against solar exposure.\n\n"
            "- **Recommended Species**: *Azadirachta indica* (Neem), *Pongamia pinnata* (Karanj), and *Cassia fistula* (Amaltas).\n"
            "- **Cooling rate**: Each 10% increase in canopy cover drops localized ambient temperatures by **2.2°C** via shading and evapotranspiration.\n"
            "- **Placement**: Target pedestrian roads and parks located over 1km away from existing green grids."
        )
        return {"text": response}

    if "blue" in msg or "water" in msg or "pond" in msg or "lake" in msg:
        response = (
            "### Blue Infrastructure & Evaporative Parks\n\n"
            "Blue corridors (lakes, fountains, and swales) act as local microclimate heat sinks.\n\n"
            "- **Advantage**: Water bodies absorb solar energy and lower surrounding air temperatures by **1.5°C to 3.0°C** through evaporation.\n"
            "- ** Ahmedabad Focus**: Areas flanking the Sabarmati River or surrounding lakes (like *Vastrapur* or *Kankaria*) show distinct cooling pockets. Wards isolated from water corridors (> 1200m) are prioritized for artificial fountains and cooling swales."
        )
        return {"text": response}

    if "hvi" in msg or "vulnerability" in msg:
        response = (
            "### Heat Vulnerability Index (HVI)\n\n"
            "Our HVI score is synthesized from three primary ecological dimensions:\n"
            "1. **Exposure**: Mean land surface temperature and p90 peaks.\n"
            "2. **Sensitivity**: Census socio-demographics (pop density, literacy, child ratio, non-workers).\n"
            "3. **Adaptive Capacity**: Density of local canopy (NDVI), albedo, and water proximity.\n\n"
            "Ahmedabad wards are divided into quantiles: Low, Moderate, High, and Extreme. You can inspect the leaderboard in the **Analytics** tab."
        )
        return {"text": response}

    # 3. Default Response
    response = (
        "I am ready to help you plan! You can ask me about:\n"
        "- Specific wards (e.g. *'What is the risk in Dariyapur?'* or *'Tell me about Bapu Nagar'*\n"
        "- Shading and cooling options (e.g. *'How do cool roofs work?'* or *'What trees should we plant?'*)\n"
        "- Specific indices (e.g. *'Explain HVI'* or *'Show correlation statistics'*)"
    )
    return {"text": response}


def json_parse(geojson_str: str) -> dict:
    import json
    return json.loads(geojson_str)

