"""
ATMOSCHAIN — FastAPI Backend
plasmasim_routes.py

Routes for plasma gasification simulation.

Endpoints:
  POST /api/simulate    — run full plasma simulation
  GET  /api/gas-types   — get supported waste types and their gas profiles

Author: ATMOSCHAIN Dev Team
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from simulation.plasma_reactor_sim import PlasmaReactorSim
from ml_models.plasmasim_models.gas_yield_predictor import GAS_COMPOSITION_DB
from ml_models.plasmasim_models.energy_prediction import NET_KWH_PER_TONNE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["PlasmaSim"])

_sim = PlasmaReactorSim()


class SimulateRequest(BaseModel):
    waste_class: str
    mass_kg: float
    scale_factor: Optional[float] = 1.0    # for scaling to industrial volumes


@router.post("/simulate")
async def simulate_plasma(request: SimulateRequest):
    """
    Run a full plasma gasification simulation.
    Returns stage-by-stage state, gas composition, energy output.
    """
    try:
        if request.mass_kg <= 0:
            raise HTTPException(status_code=400, detail="mass_kg must be positive")

        scaled_mass = request.mass_kg * (request.scale_factor or 1.0)
        result = _sim.run(request.waste_class, scaled_mass)
        return {"success": True, **result}

    except Exception as e:
        logger.error(f"Simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gas-types")
async def get_gas_types():
    """Returns supported waste types and their gas profiles."""
    profiles = {}
    for wc, fractions in GAS_COMPOSITION_DB.items():
        profiles[wc] = {
            "gas_composition_pct": {
                "H2": fractions[0], "CO": fractions[1], "CO2": fractions[2],
                "CH4": fractions[3], "N2": fractions[4], "Other": fractions[5]
            },
            "net_kwh_per_tonne": NET_KWH_PER_TONNE.get(wc, 500)
        }
    return {"waste_types": profiles}


@router.get("/plant-scenario")
async def get_plant_scenario():
    """Returns a 100 tonne/day plant scenario for Delhi MSW."""
    from backend.services.energy_estimator import estimate_plant_energy
    composition = {
        "organic": 0.50, "paper": 0.12, "plastic": 0.10,
        "textile": 0.06, "metal": 0.02, "glass": 0.02,
        "inert": 0.08, "mixed": 0.10
    }
    return {
        "plant_name"  : "Delhi WtE Plasma Plant — 100 t/day",
        "composition" : composition,
        "energy_stats": estimate_plant_energy(composition, 100.0),
        "notes": "Based on average Delhi MSW composition from CPCB India data."
    }
