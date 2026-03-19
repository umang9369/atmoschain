"""
ATMOSCHAIN — Backend Services
methane_engine.py

Service wrapper around MethanePredictor for use by FastAPI routes.
Adds detection result integration and formatted output.

Author: ATMOSCHAIN Dev Team
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ml_models.methane_model.methane_prediction import MethanePredictor


_predictor = MethanePredictor()


def calculate_methane_impact(waste_class: str, mass_kg: float, doc_override: float = None) -> dict:
    """
    Calculate full methane + CO2e + carbon credit data for a detected waste item.
    
    Args:
        waste_class  : Detected waste class string
        mass_kg      : Estimated waste mass in kilograms
        doc_override : Optional DOC value override
    
    Returns:
        Full methane impact dict from MethanePredictor
    """
    return _predictor.predict(waste_class, mass_kg, doc_override)


def calculate_from_detection(detection_result: dict) -> dict:
    """
    Convenience wrapper: takes a WasteDetector result dict directly.
    
    Args:
        detection_result: dict from waste_detector.detect_from_base64()
    
    Returns:
        Combined detection + methane impact dict
    """
    waste_class = detection_result.get("waste_class", "unknown")
    mass_kg     = detection_result.get("estimated_mass_kg", 0.1)

    methane_data = _predictor.predict(waste_class, mass_kg)

    return {
        **detection_result,
        "methane_data": methane_data,
    }


def get_ghazipur_landfill_stats() -> dict:
    """Returns daily methane stats for Ghazipur landfill scenario."""
    return _predictor.ghazipur_scenario()
