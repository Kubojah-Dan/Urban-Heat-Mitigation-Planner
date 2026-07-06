"""
UrbanCool AI — Phase 3: Analytical Modeling & Model Orchestrator
backend/src/models/train_all.py

Orchestrates Phase 3 modeling tasks:
  1. Computes Exposure, Sensitivity, Adaptive Capacity, and Heat Vulnerability Index (HVI) per ward.
  2. Classes wards into Low, Moderate, High, and Extreme vulnerability zones.
  3. Trains and evaluates short-term predictive regression models (RF & XGBoost).
  4. Saves HVI classifications and trained model binary.

Usage:
  python -m src.models.train_all
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Set up module logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(module)-15s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("train_all")

# Insert parent path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.hvi_model import update_processed_datasets
from src.models.predictive_risk import train_predictive_models


def run_pipeline():
    log.info("=" * 60)
    log.info("  Phase 3: Model Ingestion & Training Pipeline")
    log.info("=" * 60)

    # ── Step 1: HVI Assessment ───────────────────────────────────────────────
    log.info("[1/2] Launching Heat Vulnerability Index (HVI) Scoring ...")
    df_hvi = update_processed_datasets()

    # Vulnerability class counts
    counts = df_hvi["vulnerability_class"].value_counts()
    log.info("HVI Classification Summary:")
    for tier, count in counts.items():
        log.info("  %-12s: %d wards (%.1f%%)", tier, count, count / len(df_hvi) * 100)

    # ── Step 2: Predictive Risk ML Model ──────────────────────────────────────
    log.info("[2/2] Launching Short-Term Predictive Risk ML Model ...")
    train_predictive_models()

    log.info("=" * 60)
    log.info("  Phase 3 Model Pipeline COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
