import pytest
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
from src.api.main import app, df_wards, load_assets

@pytest.fixture(scope="session", autouse=True)
def setup_assets():
    load_assets()

client = TestClient(app)

def test_city_summary():
    """Test city-level aggregates endpoint."""
    response = client.get("/api/city-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["city_name"] == "Ahmedabad, India"
    assert "total_population" in data
    assert "avg_lst_mean" in data
    assert "avg_hvi" in data
    assert "vulnerability_counts" in data
    assert data["city_green_ratio"] > 0
    assert data["city_built_ratio"] > 0

def test_wards_geojson():
    """Test boundary maps GeoJSON endpoint."""
    response = client.get("/api/wards")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 48
    
    # Check properties injection
    first_feature = data["features"][0]
    assert "properties" in first_feature
    props = first_feature["properties"]
    assert "ward_id" in props
    assert "ward_name" in props
    assert "primary_rec_title" in props
    assert "primary_rec_score" in props

def test_ward_details():
    """Test detail metrics and interventions endpoint for a specific ward."""
    # Test valid ward (e.g., ID 21: Dariyapur)
    response = client.get("/api/wards/21")
    assert response.status_code == 200
    data = response.json()
    assert "ward_metrics" in data
    assert "recommendations" in data
    assert data["ward_metrics"]["ward_id"] == 21
    assert data["ward_metrics"]["ward_name"] == "Dariyapur"
    assert len(data["recommendations"]) == 3
    
    # Check recommendation format
    first_rec = data["recommendations"][0]
    assert "title" in first_rec
    assert "priority_score" in first_rec
    assert "cost_tier" in first_rec
    
    # Test invalid ward
    response = client.get("/api/wards/9999")
    assert response.status_code == 404

def test_predict_endpoint():
    """Test XGBoost meteorology forecast inference endpoint."""
    response = client.get("/api/predict?temp=42.0&humidity=35.0")
    assert response.status_code == 200
    data = response.json()
    assert "input_weather" in data
    assert "predictions" in data
    assert len(data["predictions"]) == 48  # Predictions for all 48 wards
    
    # Ensure temperatures are within reasonable physical ranges (25°C to 55°C)
    for wid, temp in data["predictions"].items():
        assert 25.0 <= float(temp) <= 55.0

def test_simulation_sandbox():
    """Test sandbox what-if scenario simulation endpoint."""
    payload = {
        "wardId": "21",
        "cityName": "Ahmedabad",
        "wardName": "Dariyapur",
        "baseLst": 38.6,
        "baseCanopy": 12.0,
        "baseHvi": 0.52,
        "popDensity": 42.5,
        "addedCanopy": 10.0,
        "addedCoolRoofs": 20.0
    }
    response = client.post("/api/simulation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["wardId"] == "21"
    assert data["newLst"] < 38.6  # temperature must drop
    assert data["newHvi"] < 0.52  # HVI score must drop
    assert data["temperatureDrop"] == pytest.approx(4.6, 0.01) # 10*0.22 + 20*0.12 = 4.6
    assert len(data["recommendations"]) > 0

def test_chatbot_endpoint():
    """Test AI Eco-Planning Advisor chat responses."""
    # Test strategy keywords (cool roof)
    payload = {
        "message": "Tell me about cool roofs",
        "history": []
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "cool roof" in data["text"].lower() or "albedo" in data["text"].lower()

    # Test ward keywords (Dariyapur)
    payload = {
        "message": "What is the status of Dariyapur ward?",
        "history": []
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "dariyapur" in data["text"].lower()
    assert "hvi" in data["text"].lower()
