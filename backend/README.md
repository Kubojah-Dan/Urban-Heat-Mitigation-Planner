# UrbanCool AI — Backend

## Overview
Python 3.10+ FastAPI backend that powers the geospatial analytics engine.

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Authenticate with Google Earth Engine (first time)
earthengine authenticate
# Then set your cloud project:
export GEE_PROJECT=your-google-cloud-project-id   # Linux/macOS
set GEE_PROJECT=your-google-cloud-project-id      # Windows CMD
$Env:GEE_PROJECT="your-google-cloud-project-id"  # PowerShell

# 4. Run the GEE connection diagnostic
python src/data_collection/test_gee.py
```

## Directory Layout

```
backend/
├── data/
│   ├── raw/          # Untouched downloads (LST, LULC, OSM, census)
│   ├── processed/    # Cleaned, reprojected, feature-engineered data
│   └── boundaries/   # Ward or fallback grid geometries
├── notebooks/        # Jupyter exploration notebooks (one per phase)
├── src/
│   ├── data_collection/   # GEE, OSMnx, Open-Meteo, census loaders
│   ├── features/          # Zonal stats, NDVI/NDBI processing
│   ├── models/            # Hotspot scorer, HVI, risk ML models
│   ├── recommender/       # Intervention ranking rules engine
│   └── api/               # FastAPI application & endpoints
└── tests/            # Pytest unit tests
```

## Environment Variables

| Variable              | Required | Description                                  |
|-----------------------|----------|----------------------------------------------|
| `GEE_PROJECT`         | Yes      | Google Cloud project ID linked to Earth Engine|
| `GEE_SERVICE_ACCOUNT` | Optional | Service-account email (for headless/CI runs) |
| `GEE_KEY_FILE`        | Optional | Path to service-account JSON key file        |

## Running the API (Phase 5+)

```bash
uvicorn src.api.main:app --reload --port 8000
```
