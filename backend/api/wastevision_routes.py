"""
ATMOSCHAIN — FastAPI Backend
wastevision_routes.py

Routes for waste detection, methane calculation, and heatmap data.

Endpoints:
  POST /api/detect      — detect waste from base64 webcam image
  GET  /api/heatmap     — Ghazipur/Delhi landfill heat zone data
  GET  /api/landfill    — Ghazipur daily emission scenario

Author: ATMOSCHAIN Dev Team
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ml_models.wastevision.waste_detector import WasteDetector
from backend.services.methane_engine import calculate_methane_impact, get_ghazipur_landfill_stats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["WasteVision"])

# Initialize detector once (reused across requests)
_detector: Optional[WasteDetector] = None

def get_detector() -> WasteDetector:
    global _detector
    if _detector is None:
        _detector = WasteDetector()
    return _detector


# ─── Request / Response Models ────────────────────────────────────────────────

class DetectRequest(BaseModel):
    image_b64: str              # base64 JPEG from webcam
    mass_override_kg: Optional[float] = None   # optional manual mass

class DetectResponse(BaseModel):
    success: bool
    detection: dict
    methane: dict
    combined: dict


# ─── Ghazipur heat zone data (based on NASA/MODIS surface temp data) ──────────
# Lat/lng grid around Ghazipur, Delhi with relative heat intensity (0–1)
GHAZIPUR_HEATMAP = {
    "center": {"lat": 28.6217, "lng": 77.3200},
    "name"  : "Ghazipur Landfill, Delhi",
    "area_hectares": 286,
    "height_meters": 65,
    "daily_input_tonnes": 2800,
    "zones": [
        {"lat": 28.6217, "lng": 77.3200, "intensity": 1.0,  "label": "Landfill core (hottest)", "temp_above_ambient_c": 5.2},
        {"lat": 28.6230, "lng": 77.3215, "intensity": 0.85, "label": "Active dumping zone",      "temp_above_ambient_c": 4.4},
        {"lat": 28.6200, "lng": 77.3185, "intensity": 0.80, "label": "Methane venting zone",     "temp_above_ambient_c": 4.1},
        {"lat": 28.6245, "lng": 77.3190, "intensity": 0.65, "label": "Leachate runoff area",     "temp_above_ambient_c": 3.4},
        {"lat": 28.6190, "lng": 77.3225, "intensity": 0.55, "label": "Perimeter buffer",         "temp_above_ambient_c": 2.8},
        {"lat": 28.6260, "lng": 77.3170, "intensity": 0.45, "label": "Outer edge (smoke)",       "temp_above_ambient_c": 2.3},
        {"lat": 28.6175, "lng": 77.3250, "intensity": 0.30, "label": "Residential fringe",       "temp_above_ambient_c": 1.5},
        {"lat": 28.6280, "lng": 77.3230, "intensity": 0.15, "label": "Yamuna river bank",        "temp_above_ambient_c": 0.8},
    ],
    "plantation_recommendations": [
        {
            "lat": 28.6260, "lng": 77.3260,
            "area_sq_m": 5000,
            "species": ["Peepal", "Neem", "Arjuna", "Eucalyptus"],
            "reasons": "Northern wind buffer + shade corridor. Estimated 3°C cooling effect.",
            "priority": "HIGH"
        },
        {
            "lat": 28.6190, "lng": 77.3150,
            "area_sq_m": 8000,
            "species": ["Bamboo", "Vetiver grass", "Moringa"],
            "reasons": "Leachate absorption + western sun shield. Prevents runoff to Yamuna.",
            "priority": "HIGH"
        },
        {
            "lat": 28.6175, "lng": 77.3200,
            "area_sq_m": 3000,
            "species": ["Tulsi", "Lantana", "Neem"],
            "reasons": "Residential fringe air purification. VOC absorption.",
            "priority": "MEDIUM"
        }
    ],
    "data_source": "NASA MODIS Land Surface Temperature + CPCB India open data",
    "last_updated": "2026-03-07"
}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/detect", response_model=None)
async def detect_waste(request: DetectRequest):
    """
    Detect waste from a webcam frame (base64 JPEG).
    Returns waste class, mass estimate, methane potential, CO2e, and carbon credits.
    """
    try:
        detector = get_detector()
        detection = detector.detect_from_base64(request.image_b64)

        # If detector failed, it returns a fallback dict with an 'error' key
        if detection.get("error"):
            return {
                "success": False,
                "detail": detection["error"]
            }

        # Use override mass if provided
        mass_kg = request.mass_override_kg or detection.get("estimated_mass_kg", 0.1)
        detection["estimated_mass_kg"] = mass_kg

        # Methane impact calculation
        methane = calculate_methane_impact(
            detection.get("waste_class", "unknown"),
            mass_kg
        )

        return {
            "success"  : True,
            "detection": detection,
            "methane"  : methane,
            "combined" : {
                "waste_class"    : detection.get("waste_class"),
                "confidence"     : detection.get("confidence"),
                "item"           : detection.get("item_description"),
                "mass_kg"        : mass_kg,
                "ch4_kg"         : methane.get("ch4_kg"),
                "co2e_kg"        : methane.get("co2e_kg"),
                "co2e_tonnes"    : methane.get("co2e_tonnes"),
                "carbon_credits" : methane.get("carbon_credits"),
                "revenue_usd_mid": methane.get("revenue_usd_mid"),
                "revenue_inr_mid": methane.get("revenue_inr_mid"),
                "biodegradable"  : detection.get("biodegradable"),
                "recyclable"     : detection.get("recyclable"),
                "hazardous"      : detection.get("hazardous"),
            }
        }

    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=f"Detector not configured: {e}")
    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap")
async def get_heatmap():
    """
    Returns Ghazipur landfill heat zone data with plantation recommendations.
    Based on NASA MODIS surface temperature data.
    """
    return GHAZIPUR_HEATMAP


@router.get("/landfill")
async def get_landfill_scenario():
    """Returns daily methane emission scenario for Ghazipur landfill."""
    return {
        "landfill": "Ghazipur, Delhi",
        "daily_stats": get_ghazipur_landfill_stats(),
        "context": {
            "input_tonnes_day": 2800,
            "operational_since": 1984,
            "current_height_m": 65,
            "legal_limit_m": 20,
            "area_hectares": 286,
            "status": "OVERFLOWING — Beyond legal height limit",
            "population_affected": 150000,
            "nearest_residential_m": 500
        }
    }
