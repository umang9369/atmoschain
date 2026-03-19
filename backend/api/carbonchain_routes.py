"""
ATMOSCHAIN — FastAPI Backend
carbonchain_routes.py

Routes for carbon credit minting, marketplace, and trading.

Endpoints:
  POST /api/mint        — mint credits from detection result
  GET  /api/market      — get marketplace listings and buyers
  POST /api/buy         — execute a trade
  GET  /api/ledger      — all minted credit records
  GET  /api/transactions— all trade history
  GET  /api/impact      — aggregated environmental impact

Author: ATMOSCHAIN Dev Team
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.carbon_credit_engine import CarbonCreditEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["CCTS"])

_engine = CarbonCreditEngine()


class MintRequest(BaseModel):
    detection_result: dict
    methane_data: dict
    minter_address: Optional[str] = None


class BuyRequest(BaseModel):
    credit_id: str
    buyer_id: str
    quantity: float


@router.post("/mint")
async def mint_credits(request: MintRequest):
    """Mint carbon credits from a waste detection + methane calculation."""
    try:
        result = _engine.mint_credits(
            request.detection_result,
            request.methane_data,
            request.minter_address
        )
        return result
    except Exception as e:
        logger.error(f"Mint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market")
async def get_market():
    """Return marketplace listings, buyer demand, and market stats."""
    return _engine.get_marketplace()


@router.post("/buy")
async def buy_credits(request: BuyRequest):
    """Execute a carbon credit trade."""
    try:
        result = _engine.execute_trade(
            request.credit_id,
            request.buyer_id,
            request.quantity
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("reason"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ledger")
async def get_ledger():
    """Return all minted carbon credit records."""
    return {"ledger": _engine.get_ledger(), "count": len(_engine.get_ledger())}


@router.get("/transactions")
async def get_transactions():
    """Return all trade transaction history."""
    txns = _engine.get_transactions()
    return {"transactions": txns, "count": len(txns)}


@router.get("/impact")
async def get_impact():
    """Return aggregated environmental impact summary."""
    return _engine.get_impact_summary()
