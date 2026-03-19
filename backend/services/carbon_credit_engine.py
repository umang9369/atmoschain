"""
ATMOSCHAIN — Backend Services
carbon_credit_engine.py

Manages carbon credit ledger, minting, and marketplace.
Uses an in-memory ledger for hackathon demo (simulates blockchain behavior).

For production: replace ledger with actual web3.py calls to CCT smart contract.

Author: ATMOSCHAIN Dev Team
"""

import uuid
import time
from datetime import datetime
from typing import Optional


# ─── In-memory blockchain ledger ──────────────────────────────────────────────

_ledger: list[dict] = []       # All minted credit records
_marketplace: list[dict] = []  # Active sell listings
_transactions: list[dict] = [] # All buy/sell transactions

# Pre-seeded credits from existing projects (as described in project spec)
_SEEDED_CREDITS = [
    {
        "id"      : "CCT-SEED-001",
        "source"  : "Reforestation — Aravalli Hills, Faridabad (800 ha)",
        "credits" : 12500.0,
        "price_usd": 18.5,
        "available": 8200.0,
        "minted_at": "2025-06-01",
        "category" : "nature_based"
    },
    {
        "id"      : "CCT-SEED-002",
        "source"  : "Solar Farm — Rajasthan (50 MW)",
        "credits" : 25000.0,
        "price_usd": 15.0,
        "available": 19500.0,
        "minted_at": "2025-08-15",
        "category" : "renewable_energy"
    },
    {
        "id"      : "CCT-SEED-003",
        "source"  : "Methane Capture — Ghazipur Landfill Pilot",
        "credits" : 5200.0,
        "price_usd": 22.0,
        "available": 5200.0,
        "minted_at": "2025-11-20",
        "category" : "methane_capture"
    },
    {
        "id"      : "CCT-SEED-004",
        "source"  : "Energy Efficiency — Delhi Metro Regenerative Braking",
        "credits" : 3800.0,
        "price_usd": 12.0,
        "available": 2100.0,
        "minted_at": "2026-01-10",
        "category" : "energy_efficiency"
    },
]

# Pre-configured industry buyers
INDUSTRY_BUYERS = [
    {"id": "BUY-001", "name": "IndiGo Airlines",          "sector": "Aviation",    "budget_usd": 150000, "demand_tonnes": 5000},
    {"id": "BUY-002", "name": "UltraTech Cement",         "sector": "Cement",      "budget_usd": 200000, "demand_tonnes": 8000},
    {"id": "BUY-003", "name": "Tata Steel",                "sector": "Steel",       "budget_usd": 300000, "demand_tonnes": 12000},
    {"id": "BUY-004", "name": "Reliance Industries",       "sector": "Petrochemical","budget_usd": 500000,"demand_tonnes": 20000},
    {"id": "BUY-005", "name": "NTPC (Coal Division)",      "sector": "Utilities",   "budget_usd": 400000, "demand_tonnes": 15000},
    {"id": "BUY-006", "name": "JSW Paints",                "sector": "Manufacturing","budget_usd": 50000,  "demand_tonnes": 2000},
    {"id": "BUY-007", "name": "Air India",                 "sector": "Aviation",    "budget_usd": 120000, "demand_tonnes": 4000},
    {"id": "BUY-008", "name": "Ambuja Cement",             "sector": "Cement",      "budget_usd": 180000, "demand_tonnes": 7000},
]

USD_TO_INR = 92


class CarbonCreditEngine:
    """
    Manages the full carbon credit lifecycle:
      1. Minting from methane impact data
      2. Listing on marketplace
      3. Executing trades
    """

    def __init__(self):
        # Initialize with seeded credits
        for s in _SEEDED_CREDITS:
            _marketplace.append(s.copy())

    def mint_credits(
        self,
        detection_result: dict,
        methane_data: dict,
        minter_address: Optional[str] = None
    ) -> dict:
        """
        Mint new carbon credits based on waste detection + methane calculation.
        
        Args:
            detection_result: From WasteDetector
            methane_data    : From MethanePredictor
            minter_address  : Wallet address (optional, for blockchain)
        
        Returns:
            Minted credit record
        """
        credits = methane_data.get("carbon_credits", 0.0)
        if credits <= 0:
            return {
                "success": False,
                "reason": f"No carbon credits generated for {detection_result.get('waste_class')} waste (non-biodegradable or zero methane potential).",
                "credits_minted": 0.0
            }

        token_id = f"CCT-WV-{str(uuid.uuid4())[:8].upper()}"
        record = {
            "id"              : token_id,
            "source"          : f"WasteVision Detection — {detection_result.get('item_description', 'Waste item')}",
            "waste_class"     : detection_result.get("waste_class"),
            "mass_kg"         : detection_result.get("estimated_mass_kg"),
            "credits"         : round(credits, 8),
            "available"       : round(credits, 8),
            "price_usd"       : 20.0,
            "price_inr"       : round(20.0 * USD_TO_INR, 2),
            "co2e_tonnes"     : methane_data.get("co2e_tonnes", 0),
            "ch4_kg"          : methane_data.get("ch4_kg", 0),
            "minted_at"       : datetime.now().isoformat(),
            "minter"          : minter_address or "0xATMOSCHAIN_DEMO",
            "category"        : "methane_capture",
            "tx_hash"         : f"0x{uuid.uuid4().hex[:40]}",
            "revenue_usd_mid" : methane_data.get("revenue_usd_mid", 0),
            "revenue_inr_mid" : methane_data.get("revenue_inr_mid", 0),
        }

        _ledger.append(record)
        _marketplace.append(record.copy())

        return {
            "success"        : True,
            "token_id"       : token_id,
            "credits_minted" : round(credits, 8),
            "revenue_usd"    : round(credits * 20.0, 4),
            "revenue_inr"    : round(credits * 20.0 * USD_TO_INR, 2),
            "tx_hash"        : record["tx_hash"],
            "record"         : record,
        }

    def get_ledger(self) -> list:
        """Return all minted credit records."""
        return _ledger + _SEEDED_CREDITS

    def get_marketplace(self) -> dict:
        """Return marketplace listings + buyer demand."""
        total_available = sum(m.get("available", 0) for m in _marketplace)
        total_value_usd = sum(
            m.get("available", 0) * m.get("price_usd", 20.0)
            for m in _marketplace
        )
        return {
            "listings"      : _marketplace,
            "buyers"        : INDUSTRY_BUYERS,
            "total_credits_available": round(total_available, 4),
            "total_value_usd"        : round(total_value_usd, 2),
            "total_value_inr"        : round(total_value_usd * USD_TO_INR, 2),
            "avg_price_usd"          : 18.7,
            "market_trend"           : "BULLISH",
            "price_change_30d_pct"   : 12.4,
        }

    def execute_trade(self, credit_id: str, buyer_id: str, quantity: float) -> dict:
        """
        Execute a carbon credit trade between a listing and a buyer.
        
        Returns:
            Trade record with transaction hash
        """
        # Find listing
        listing = next((m for m in _marketplace if m["id"] == credit_id), None)
        buyer   = next((b for b in INDUSTRY_BUYERS if b["id"] == buyer_id), None)

        if not listing:
            return {"success": False, "reason": "Credit listing not found"}
        if not buyer:
            return {"success": False, "reason": "Buyer not found"}
        if quantity > listing.get("available", 0):
            return {"success": False, "reason": "Insufficient credits available"}

        price_usd = listing.get("price_usd", 20.0)
        total_cost_usd = round(quantity * price_usd, 4)
        total_cost_inr = round(total_cost_usd * USD_TO_INR, 2)

        # Update available
        listing["available"] = round(listing["available"] - quantity, 8)

        tx = {
            "tx_hash"       : f"0x{uuid.uuid4().hex[:40]}",
            "credit_id"     : credit_id,
            "buyer_id"      : buyer_id,
            "buyer_name"    : buyer["name"],
            "quantity"      : round(quantity, 4),
            "price_usd"     : price_usd,
            "total_usd"     : total_cost_usd,
            "total_inr"     : total_cost_inr,
            "timestamp"     : datetime.now().isoformat(),
            "status"        : "CONFIRMED",
        }
        _transactions.append(tx)

        return {"success": True, "transaction": tx}

    def get_transactions(self) -> list:
        """Return all trade transactions."""
        return _transactions

    def get_impact_summary(self) -> dict:
        """Return aggregated environmental impact from all minted credits."""
        total_credits  = sum(r.get("credits", 0) for r in _ledger)
        total_co2e     = sum(r.get("co2e_tonnes", 0) for r in _ledger)
        total_ch4      = sum(r.get("ch4_kg", 0) for r in _ledger)
        total_revenue  = total_credits * 20.0

        return {
            "total_credits_minted" : round(total_credits, 4),
            "total_co2e_avoided_t" : round(total_co2e, 4),
            "total_ch4_avoided_kg" : round(total_ch4, 4),
            "total_revenue_usd"    : round(total_revenue, 2),
            "total_revenue_inr"    : round(total_revenue * USD_TO_INR, 2),
            "transactions_count"   : len(_transactions),
            "equivalent_trees"     : round(total_co2e * 40.0),  # 1 tree ≈ 25 kg CO2/year for 40 years
            "equivalent_cars_off_road": round(total_co2e / 4.6),   # avg car = 4.6 t CO2/year
        }
