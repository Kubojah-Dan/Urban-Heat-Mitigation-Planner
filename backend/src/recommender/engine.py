"""
UrbanCool AI — Phase 4: Cool Mitigation Recommendation Engine
backend/src/recommender/engine.py

Matches a ward's spatiotemporal and socio-physical features to targeted cool interventions:
  1. Cool Roofs (Albedo Coating)
  2. Urban Forestry (Canopy Expansion)
  3. Reflective Pavements (Cool Streets)
  4. Blue Infrastructure (Evaporative Water Bodies)
  5. Green Roofs / Vertical Greenery (Dense Core Cooling)

The engine computes suitability scores (0-100) using multi-criteria rules,
ranks them, and returns the top 3 strategies along with dynamic, metric-driven rationales.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"


# ── Strategies Metadata ───────────────────────────────────────────────────────
STRATEGIES = {
    "cool_roofs": {
        "title": "Cool Roofs (Albedo Enhancement)",
        "description": "Apply high-albedo elastomeric coatings on building roofs to reflect solar radiation and lower indoor and ambient air temperatures.",
        "cost_tier": "Low",
        "impact_potential": "High",
    },
    "urban_forestry": {
        "title": "Urban Forestry & Tree Canopies",
        "description": "Plant native, drought-resistant shade trees along streets and open spaces to maximize cooling through shade and evapotranspiration.",
        "cost_tier": "Medium",
        "impact_potential": "High",
    },
    "reflective_pavements": {
        "title": "Reflective & Cool Pavements",
        "description": "Resurface roadways and parking lots with light-colored, reflective coatings or permeable pavers to reduce solar heat storage in asphalt.",
        "cost_tier": "Medium",
        "impact_potential": "Medium",
    },
    "blue_infrastructure": {
        "title": "Blue Infrastructure & Fountain Parks",
        "description": "Construct small retention ponds, bioswales, or public fountain plazas to provide local evaporative cooling and rest areas.",
        "cost_tier": "High",
        "impact_potential": "Medium-High",
    },
    "green_roofs": {
        "title": "Green Roofs & Vertical Gardens",
        "description": "Install vegetated soil layers on flat roofs and trellised wall greenery to insulate buildings and combat heat in zero-ground-space zones.",
        "cost_tier": "High",
        "impact_potential": "Medium",
    }
}


def get_recommendations_for_ward(ward_id: int, df_wards: pd.DataFrame | None = None) -> list[dict]:
    """
    Generate scored, prioritized recommendations with logic rationales for a single ward.
    """
    if df_wards is None:
        csv_path = PROCESSED_DIR / "features_wards.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Ward features CSV not found: {csv_path}. Run Phase 3 first.")
        df_wards = pd.read_csv(csv_path)

    # Find ward row
    ward_rows = df_wards[df_wards["ward_id"] == ward_id]
    if ward_rows.empty:
        raise ValueError(f"Ward ID {ward_id} not found in features dataset.")
    ward = ward_rows.iloc[0]

    # Extract metrics for rationales
    ward_name = ward["ward_name"]
    lst_mean = ward["LST_mean"]
    ndvi = ward["NDVI_mean"]
    built_ratio = ward["built_area_ratio"]
    road_ratio = ward["road_coverage_ratio"]
    pop_density = ward["pop_density_km2"]
    green_prox = ward["green_proximity_m"]
    water_prox = ward["water_proximity_m"]

    # Extract normalised variables for scoring (0 to 1 range)
    lst_mean_n   = ward.get("LST_mean_norm", 0.5)
    lst_p90_n    = ward.get("LST_p90_norm", 0.5)
    ndvi_n       = ward.get("NDVI_mean_norm", 0.5)
    ndbi_n       = ward.get("NDBI_mean_norm", 0.5)
    built_n      = ward.get("built_area_ratio_norm", 0.5)
    road_n       = ward.get("road_coverage_ratio_norm", 0.5)
    green_n      = ward.get("green_area_ratio_norm", 0.0)
    green_prox_n = ward.get("green_proximity_m_norm", 0.5)
    water_prox_n = ward.get("water_proximity_m_norm", 0.5)
    pop_n        = ward.get("pop_density_km2_norm", 0.5)

    scores = {}
    rationales = {}

    # ── 1. Cool Roofs Score ───────────────────────────────────────────────────
    # Priority: High built density, low vegetation, high surface temperatures
    cool_roof_score = (0.45 * built_n + 0.35 * (1 - ndvi_n) + 0.20 * lst_mean_n) * 100
    scores["cool_roofs"] = round(cool_roof_score, 1)
    rationales["cool_roofs"] = (
        f"Selected as a priority because {ward_name} has a built-up area ratio of {built_ratio:.1%} "
        f"and a vegetation index (NDVI) of {ndvi:.2f}, indicating a high concentration of roofing surfaces "
        f"absorbing solar heat, suitable for albedo-enhancing coatings."
    )

    # ── 2. Urban Forestry Score ───────────────────────────────────────────────
    # Priority: High vegetation deficit, far from green spaces, high population density
    forestry_score = (0.40 * (1 - ndvi_n) + 0.35 * green_prox_n + 0.25 * pop_n) * 100
    scores["urban_forestry"] = round(forestry_score, 1)
    rationales["urban_forestry"] = (
        f"Recommended to expand tree canopy since {ward_name} is located {green_prox:.0f}m away "
        f"from nearest urban parks (above city median) and supports a high population density of "
        f"{pop_density:.0f}/km², maximizing the social and health benefits of shade cooling."
    )

    # ── 3. Reflective Pavements Score ─────────────────────────────────────────
    # Priority: High road coverage ratio, high built-up, high baseline temperatures
    pavement_score = (0.50 * road_n + 0.30 * built_n + 0.20 * lst_mean_n) * 100
    scores["reflective_pavements"] = round(pavement_score, 1)
    rationales["reflective_pavements"] = (
        f"Indicated due to a high road pavement coverage ratio of {road_ratio:.1%}, "
        f"implying that standard dark asphalt surfaces are storing daytime solar energy and "
        f"contributing to elevated local surface temperatures ({lst_mean:.1f}°C)."
    )

    # ── 4. Blue Infrastructure Score ──────────────────────────────────────────
    # Priority: Far from water, low water area, high peak thermal exposure
    blue_score = (0.40 * water_prox_n + 0.30 * (1 - ndvi_n) + 0.30 * lst_p90_n) * 100
    scores["blue_infrastructure"] = round(blue_score, 1)
    rationales["blue_infrastructure"] = (
        f"Selected because {ward_name} is currently isolated from cooling water corridors "
        f"(nearest water body is {water_prox:.0f}m away) and experiences severe peak heat exposure "
        f"up to {ward['LST_p90']:.1f}°C (90th percentile), making micro-scale evaporative cooling parks valuable."
    )

    # ── 5. Green Roofs Score ──────────────────────────────────────────────────
    # Priority: Extreme building density, high built ratio, zero ground space for tree planting
    green_roof_score = (0.50 * built_n + 0.30 * (1 - green_n) + 0.20 * pop_n) * 100
    # Deduct score if there is already plenty of greenspace (unlikely in dense cores)
    green_roof_score = max(0, green_roof_score - (30 * green_n))
    scores["green_roofs"] = round(green_roof_score, 1)
    rationales["green_roofs"] = (
        f"Recommended for dense cores: {ward_name} suffers from a severe lack of ground-level park space "
        f"(green space coverage is {ward['green_area_ratio']:.2%}) and high building density, "
        f"meaning retrofitting flat rooftops and structural walls with green layers is the primary path to add insulation."
    )

    # ── Compile and Sort ──────────────────────────────────────────────────────
    recommendations = []
    for key, meta in STRATEGIES.items():
        recommendations.append({
            "key": key,
            "title": meta["title"],
            "description": meta["description"],
            "cost_tier": meta["cost_tier"],
            "impact_potential": meta["impact_potential"],
            "priority_score": scores[key],
            "rationale": rationales[key]
        })

    # Sort descending by priority score and take top 3
    recommendations = sorted(recommendations, key=lambda x: x["priority_score"], reverse=True)[:3]

    return recommendations


if __name__ == "__main__":
    import json
    # Simple test for a couple of different profiles
    csv_path = PROCESSED_DIR / "features_wards.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)

        # 1. Hot, dense core ward: Bapu Nagar (ward_id = 26)
        print("\n" + "=" * 80)
        print("RECOMMENDATION TEST: Bapu Nagar (Dense Urban Core)")
        print("=" * 80)
        recs_dense = get_recommendations_for_ward(26, df)
        print(json.dumps(recs_dense, indent=2))

        # 2. Lower density suburban ward: Thaltej (ward_id = 8)
        print("\n" + "=" * 80)
        print("RECOMMENDATION TEST: Thaltej (Suburban/Developed)")
        print("=" * 80)
        recs_suburban = get_recommendations_for_ward(8, df)
        print(json.dumps(recs_suburban, indent=2))
