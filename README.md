# UrbanCool AI

> **Satellite-driven urban heat mitigation planner** — Pilot city: Ahmedabad, India

UrbanCool AI fuses satellite remote-sensing data, open-source GIS layers, and machine-learning analytics into an interactive planning dashboard that helps municipal engineers and urban planners evaluate thermal exposure and design cooling interventions.

---

## Architecture

```
Data sources (GEE / OSM / Census)
        │
        ▼
Feature Layer (LST · NDVI · NDBI · Albedo)
        │
        ▼
AI/ML Models (Hotspot Ranker · HVI · Risk Regressor)
        │
        ▼
Decision Engine (Intervention Rules Matrix)
        │
        ▼
Planner Dashboard (React · Leaflet Choropleth Map)
```

---

## Repository Structure

```
urbancool-ai/
├── backend/
│   ├── data/
│   │   ├── raw/          # Untouched satellite/GIS downloads
│   │   ├── processed/    # Feature-engineered outputs
│   │   └── boundaries/   # Ward polygons (amc_wards.geojson)
│   ├── src/
│   │   ├── data_collection/  # GEE · OSMnx · Open-Meteo · Census loaders
│   │   ├── features/         # Zonal stats · index computation
│   │   ├── models/           # HVI Scoring & XGBoost ML model code
│   │   ├── recommender/      # Intervention rules engine
│   │   └── api/              # FastAPI REST endpoints
│   ├── tests/            # Pytest suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # Header · Sidebar · MapView · Inspector · Panels
│   │   ├── hooks/        # useWardData
│   │   └── index.css     # Tailwind CSS & custom design variables
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## Build Phases

| Phase | Focus                            | Status      |
|-------|----------------------------------|-------------|
| 0     | Setup & GEE Connection           | ✅ Complete |
| 1     | Data Collection Infrastructure   | ✅ Complete |
| 2     | Preprocessing & Feature Engineering | ✅ Complete |
| 3     | Modeling & Risk Assessment       | ✅ Complete |
| 4     | Recommendation Engine            | ✅ Complete |
| 5     | API & React Dashboard            | ✅ Complete |
| 6     | Validation & Deployment          | ✅ Complete |

---

## Technical Documentation & Setup Guide

### 1. Prerequisites
- **Python**: Version 3.10+ (recommend 3.10.11 or higher)
- **Node.js**: Version 18+ and `npm` package manager
- **Google Cloud SDK**: Set up and authorized with access to Google Earth Engine (GEE).

---

### 2. Backend Installation & Start
The backend is powered by FastAPI, loading in-memory census data, spatial ward outlines, and an XGBoost regression model binary.

```bash
# 1. Enter backend directory
cd backend

# 2. Create virtual environment and activate
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# 3. Install packages
pip install -r requirements.txt

# 4. Create and define environment file (.env)
# Create a .env file under backend/ with your active GEE project ID:
GEE_PROJECT=urbancool-ai-501315

# 5. Launch FastAPI development server
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

The REST API endpoints will be online at `http://127.0.0.1:8000/docs`.

---

### 3. Frontend Installation & Start
The frontend is built using React (Vite bundler), Leaflet GIS mapping, and Tailwind CSS v4.

```bash
# 1. Enter frontend directory
cd ../frontend

# 2. Install Node dependencies
npm install

# 3. Launch Vite development server
npm run dev
```

The UI dashboard portal will boot at `http://localhost:5173/`.

---

### 4. Running the Automated Test Suite
We use `pytest` and `httpx` to run end-to-end endpoint and prediction validation checks.

```bash
# 1. Enter backend directory and activate virtual env
cd backend
.venv\Scripts\activate

# 2. Run pytest suite
python -m pytest tests/
```

The test runner validates:
- API connectivity and payload structures.
- Spatial GeoJSON formatting and property injections.
- XGBoost risk forecaster temperature predictions.
- What-If sandbox simulation parameter formulas and reductions.
- AI Chatbot heuristical keyword mapping.

---

## Core Analytics & ML Specifications

### Heat Vulnerability Index (HVI)
The HVI score (0.0 to 1.0) balances three primary dimensions:
1. **Exposure**: $0.6 \times \text{LST\_p90\_normalized} + 0.4 \times \text{LST\_mean\_normalized}$
2. **Sensitivity**: $0.25 \times \text{PopDensity} + 0.2 \times \text{ChildRatio} + 0.2 \times \text{SocialGroups} + 0.2 \times \text{NonWorkerRatio} + 0.15 \times (1 - \text{LiteracyRate})$
3. **Adaptive Capacity**: $0.3 \times \text{NDVI} + 0.15 \times \text{Albedo} + 0.25 \times \text{GreenRatio} + 0.15 \times (1 - \text{GreenProximity}) + 0.15 \times (1 - \text{WaterProximity})$

### Spatiotemporal XGBoost Model
- **Target**: Land Surface Temperature (LST).
- **Features**: Apparent temperature, relative humidity, direct shortwave solar radiation, local vegetative NDVI, and built NDBI indexes.
- **Accuracy**: Trained on $17,568$ spatial-meteorological historical matrices with **RMSE: 0.2762°C**, **MAE: 0.1173°C**, and **R²: 0.9976**.

---

## Ahmedabad Heat Action Plan (HAP) Alignment
Ahmedabad was the first city in South Asia to introduce a formal Heat Action Plan in 2013. UrbanCool AI matches these standards:
- **Temperature Thresholds**: The map coloring and weather warning systems are mapped to HAP alert levels:
  - **Yellow Alert** (41°C – 43°C): Heat warning conditions.
  - **Orange Alert** (43.1°C – 44.9°C): Severe warning.
  - **Red Alert** (>= 45°C): Extreme heat wave emergency.
- **Cool Roof Focus**: The recommender prioritizes cool roof retrofits for high-density, low-albedo wards, matching the AMC (Ahmedabad Municipal Corporation) cool roofs initiative targeting vulnerable informal settlements.
- **Canopy Shading**: Prioritizes native urban forestry (*Azadirachta indica* (Neem) and *Pongamia pinnata* (Karanj)) to mitigate hot asphalt road corridors.

---

## License
MIT © UrbanCool AI Contributors
