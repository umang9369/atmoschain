"""
ATMOSCHAIN — Backend Services
energy_estimator.py

Service wrapper around EnergyPredictor for use by API routes.
Also provides combined simulation result aggregation.

Author: ATMOSCHAIN Dev Team
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ml_models.plasmasim_models.energy_prediction import EnergyPredictor

_predictor = EnergyPredictor()


def estimate_energy(waste_class: str, mass_kg: float) -> dict:
    """Estimate electricity and heat output from plasma gasification."""
    return _predictor.predict(waste_class, mass_kg)


def estimate_plant_energy(
    waste_composition: dict,
    total_tonnes_per_day: float = 100.0
) -> dict:
    """Daily plant-level energy projection."""
    return _predictor.daily_plant_scenario(waste_composition, total_tonnes_per_day)
