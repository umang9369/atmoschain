"""
ATMOSCHAIN — Analytics Module
revenue_projection.py

Financial modeling for a Plasma Gasification + CCTS plant processing
Ghazipur landfill waste.

Models three interconnected revenue streams:
  1. Electricity Export (Grid feed-in from Syngas turbines)
  2. Carbon Credit Sales (CCTS marketplace receipts per minted CCT)
  3. Slag / Vitrified Aggregate Sales (construction material by-product)

Also computes:
  - CapEx / OpEx framework for a 500 tonne/day pilot plant
  - Net Present Value (NPV) and Internal Rate of Return (IRR) estimate
  - Payback period under three carbon-price scenarios (bear, base, bull)
  - 20-year cumulative P&L projection

Reference data:
  - WTERT Plasma Gasification Technology Assessment (2022)
  - World Bank Carbon Market Report (2024)
  - CEEW Indian Waste-to-Energy Feasibility Study (2023)
  - India CERC Average Power Procurement Cost: ₹8.5 / kWh (2024)

Author: ATMOSCHAIN Dev Team
"""

import math
from typing import Optional


# ─── Plant Configuration ──────────────────────────────────────────────────────

DEFAULT_PLANT_CAPACITY_T_DAY = 500.0   # tonnes/day pilot plant
OPERATIONAL_DAYS_PER_YEAR    = 330     # accounting for maintenance shutdowns
PLANT_LIFETIME_YEARS         = 20

# Waste composition mirrors Ghazipur
GHAZIPUR_COMPOSITION = {
    "organic":  0.50,
    "paper":    0.12,
    "plastic":  0.10,
    "textile":  0.06,
    "metal":    0.02,
    "glass":    0.02,
    "inert":    0.08,
    "mixed":    0.10,
}

# Net electricity yield (kWh per tonne) — plasma arc WtE, 28% efficiency
NET_KWH_PER_TONNE = {
    "plastic": 750, "organic": 380, "paper": 500,
    "textile": 580, "wood":    620, "metal":  50,
    "glass":    30, "inert":    20, "mixed": 600,
    "unknown": 500,
}

# Slag yield (kg per tonne of waste input)
SLAG_YIELD_KG_PER_TONNE = {
    "plastic": 30,  "organic": 50,  "paper": 80,
    "textile": 60,  "wood":   100,  "metal": 800,
    "glass":  950,  "inert":  900,  "mixed": 150,
    "unknown": 200,
}

# ─── Pricing Assumptions ──────────────────────────────────────────────────────

# Grid electricity tariff (wholesale, India CERC)
ELECTRICITY_PRICE_INR_KWH = 8.50
ELECTRICITY_PRICE_USD_KWH = 0.102   # at 83.5 USD/INR

# Carbon credit price scenarios (USD per tonne CO₂e, World Bank 2024)
CARBON_PRICE_SCENARIOS = {
    "bear": 10.0,   # regulatory floor
    "base": 20.0,   # current voluntary market mid
    "bull": 35.0,   # Paris-aligned 2030 target
}

# Slag / Vitrified aggregate selling price (USD per tonne)
SLAG_PRICE_USD_TONNE = 15.0   # construction aggregate market price

# Tipping fee revenue (gate fee charged to municipalities per tonne of waste)
TIPPING_FEE_USD_TONNE = 8.0

# IPCC methane constants (duplicate from methane model for standalone use)
DOC_BY_WASTE_TYPE = {
    "plastic": 0.00, "organic": 0.15, "paper": 0.40,
    "textile": 0.24, "metal":  0.00, "glass": 0.00,
    "inert":   0.00, "mixed":  0.12, "unknown": 0.10,
}
DOCf = 0.50; F = 0.50; MCF = 1.00; GWP100 = 28; MOLAR = 16.0 / 12.0

# ─── CapEx / OpEx Model ───────────────────────────────────────────────────────

# Capital expenditure for 500 t/day plasma gasification plant (USD M)
# Based on InEnTec / AlterNRG vendor cost data
CAPEX_USD_M = {
    "plasma_reactors"        : 45.0,   # 3 × 165 t/day plasma arc units
    "gas_cleaning_system"    : 12.0,   # cyclone + scrubber + fractionation
    "power_generation_block" : 18.0,   # turbines + generators
    "civil_infrastructure"   : 22.0,   # land, roads, buildings
    "control_systems_it"     :  6.0,   # SCADA, IoT, CCTS integration
    "contingency_10pct"      : 10.3,   # 10% contingency
}
TOTAL_CAPEX_USD_M = sum(CAPEX_USD_M.values())

# Annual operating expenditure (USD M/year)
OPEX_USD_M_YEAR = {
    "labour"                 :  3.2,   # ~120 FTEs
    "electricity_parasitic"  :  2.8,   # plasma arc power consumption
    "maintenance"            :  4.5,   # 4% of CapEx annually
    "consumables_reagents"   :  1.1,   # scrubber chemicals, etc.
    "insurance_regulatory"   :  0.9,
    "administration"         :  0.5,
}
TOTAL_OPEX_USD_M_YEAR = sum(OPEX_USD_M_YEAR.values())

DISCOUNT_RATE = 0.10   # 10% WACC for Indian infrastructure projects
USD_TO_INR    = 83.5


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _annual_electricity_kwh(
    capacity_t_day: float,
    composition: dict,
    operational_days: int = OPERATIONAL_DAYS_PER_YEAR
) -> float:
    """
    Compute annual electricity generation (kWh) for a given plant capacity
    and waste composition.
    """
    daily_kwh = 0.0
    for wc, fraction in composition.items():
        mass_kg    = fraction * capacity_t_day * 1000.0
        mass_t     = mass_kg / 1000.0
        kwh_per_t  = NET_KWH_PER_TONNE.get(wc, 500)
        daily_kwh += kwh_per_t * mass_t
    return round(daily_kwh * operational_days, 2)


def _annual_slag_tonnes(
    capacity_t_day: float,
    composition: dict,
    operational_days: int = OPERATIONAL_DAYS_PER_YEAR
) -> float:
    """
    Compute annual slag production (tonnes) from vitrification.
    """
    daily_slag_kg = 0.0
    for wc, fraction in composition.items():
        mass_t         = fraction * capacity_t_day
        slag_per_t     = SLAG_YIELD_KG_PER_TONNE.get(wc, 200)
        daily_slag_kg += slag_per_t * mass_t
    return round((daily_slag_kg / 1000.0) * operational_days, 2)


def _annual_co2e_avoided(
    capacity_t_day: float,
    composition: dict,
    operational_days: int = OPERATIONAL_DAYS_PER_YEAR
) -> float:
    """
    Compute annual CO₂e avoided by diverting waste from landfill to plasma
    gasification (97% methane destruction rate).
    """
    elimination = 0.97
    daily_co2e  = 0.0
    for wc, fraction in composition.items():
        mass_t     = fraction * capacity_t_day
        doc        = DOC_BY_WASTE_TYPE.get(wc, 0.10)
        ch4_t      = mass_t * doc * DOCf * F * MCF * MOLAR
        co2e_t     = ch4_t * GWP100 * elimination
        daily_co2e += co2e_t
    return round(daily_co2e * operational_days, 4)


def _npv(cash_flows: list, discount_rate: float) -> float:
    """
    Compute Net Present Value of a series of annual cash flows (USD M),
    starting at Year 1.  Year 0 is excluded (it's the CapEx investment).
    """
    return round(
        sum(cf / ((1 + discount_rate) ** yr) for yr, cf in enumerate(cash_flows, 1)),
        4
    )


def _irr(initial_investment: float, cash_flows: list, max_iter: int = 200) -> float:
    """
    Estimate Internal Rate of Return using bisection search.

    Args:
        initial_investment: positive CapEx figure (USD M)
        cash_flows        : list of annual net cash flows (USD M)

    Returns:
        IRR as a decimal (e.g. 0.18 = 18%)
    """
    lo, hi = 0.0, 5.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        npv = -initial_investment + sum(
            cf / ((1 + mid) ** yr) for yr, cf in enumerate(cash_flows, 1)
        )
        if abs(npv) < 1e-6:
            break
        if npv > 0:
            lo = mid
        else:
            hi = mid
    return round(mid, 4)


# ─── Main Revenue Projection Class ────────────────────────────────────────────

class RevenueProjModel:
    """
    Full financial model for an ATMOSCHAIN Plasma Gasification + CCTS plant.

    Usage:
        rp = RevenueProjModel(capacity_t_day=500)
        print(rp.full_report())
    """

    def __init__(
        self,
        capacity_t_day: float            = DEFAULT_PLANT_CAPACITY_T_DAY,
        composition: Optional[dict]      = None,
        operational_days: int            = OPERATIONAL_DAYS_PER_YEAR,
        carbon_scenario: str             = "base",
    ):
        self.capacity        = capacity_t_day
        self.composition     = composition or GHAZIPUR_COMPOSITION
        self.op_days         = operational_days
        self.carbon_price    = CARBON_PRICE_SCENARIOS.get(carbon_scenario, 20.0)
        self.carbon_scenario = carbon_scenario

        # Pre-compute physical quantities
        self._kwh_year       = _annual_electricity_kwh(self.capacity, self.composition, self.op_days)
        self._slag_t_year    = _annual_slag_tonnes(self.capacity, self.composition, self.op_days)
        self._co2e_year      = _annual_co2e_avoided(self.capacity, self.composition, self.op_days)
        self._waste_t_year   = self.capacity * self.op_days

    # ── 1. Annual Revenue Breakdown ───────────────────────────────────────────

    def annual_revenue(self) -> dict:
        """
        Compute annual gross revenue in USD M broken into streams:
          - Electricity Export
          - Carbon Credit Sales (CCTS)
          - Slag / Aggregate Sales
          - Tipping Fees
        """
        rev_elec   = round(self._kwh_year * ELECTRICITY_PRICE_USD_KWH / 1e6, 4)
        rev_carbon = round(self._co2e_year * self.carbon_price / 1e6, 4)
        rev_slag   = round(self._slag_t_year * SLAG_PRICE_USD_TONNE / 1e6, 4)
        rev_tip    = round(self._waste_t_year * TIPPING_FEE_USD_TONNE / 1e6, 4)
        total      = round(rev_elec + rev_carbon + rev_slag + rev_tip, 4)

        return {
            "carbon_scenario"           : self.carbon_scenario,
            "carbon_price_usd_tonne"    : self.carbon_price,
            "electricity_revenue_usd_m" : rev_elec,
            "carbon_credit_revenue_usd_m": rev_carbon,
            "slag_revenue_usd_m"        : rev_slag,
            "tipping_fee_revenue_usd_m" : rev_tip,
            "total_gross_revenue_usd_m" : total,
            "total_gross_revenue_inr_cr": round(total * 1e6 * USD_TO_INR / 1e7, 2),  # ₹ crore
            # Revenue share breakdown (%)
            "electricity_share_pct"     : round(rev_elec   / total * 100, 1),
            "carbon_share_pct"          : round(rev_carbon / total * 100, 1),
            "slag_share_pct"            : round(rev_slag   / total * 100, 1),
            "tipping_share_pct"         : round(rev_tip    / total * 100, 1),
        }

    # ── 2. Physical Quantities Summary ───────────────────────────────────────

    def physical_summary(self) -> dict:
        """Annual physical throughput and output summary."""
        return {
            "plant_capacity_t_day"      : self.capacity,
            "operational_days_per_year" : self.op_days,
            "waste_processed_t_year"    : self._waste_t_year,
            "electricity_generated_kwh" : self._kwh_year,
            "electricity_generated_mwh" : round(self._kwh_year / 1000, 2),
            "homes_powered_annually"    : round(self._kwh_year / (100 * 12)),  # 100kWh/month
            "slag_produced_t_year"      : self._slag_t_year,
            "co2e_avoided_t_year"       : self._co2e_year,
            "carbon_credits_minted_year": self._co2e_year,   # 1 CCT = 1 tonne CO₂e
            "equivalent_cars_removed"   : round(self._co2e_year / 4.6),
            "equivalent_trees_planted"  : round(self._co2e_year * 40),
        }

    # ── 3. CapEx / OpEx Summary ───────────────────────────────────────────────

    def capex_opex_summary(self) -> dict:
        """Return full capital and operating cost breakdown."""
        annual_net = round(self.annual_revenue()["total_gross_revenue_usd_m"] - TOTAL_OPEX_USD_M_YEAR, 4)
        return {
            "capex_breakdown_usd_m"  : CAPEX_USD_M,
            "total_capex_usd_m"      : round(TOTAL_CAPEX_USD_M, 2),
            "total_capex_inr_cr"     : round(TOTAL_CAPEX_USD_M * USD_TO_INR / 100, 2),  # ₹ crore
            "opex_breakdown_usd_m"   : OPEX_USD_M_YEAR,
            "total_opex_usd_m_year"  : round(TOTAL_OPEX_USD_M_YEAR, 2),
            "net_annual_profit_usd_m": annual_net,
            "ebitda_margin_pct"      : round(annual_net / self.annual_revenue()["total_gross_revenue_usd_m"] * 100, 1),
        }

    # ── 4. NPV / IRR / Payback ────────────────────────────────────────────────

    def investment_metrics(self) -> dict:
        """
        Compute NPV, IRR, and simple payback period using the WACC-discounted
        cash flow model over the full plant lifetime.
        """
        rev_data   = self.annual_revenue()
        gross_rev  = rev_data["total_gross_revenue_usd_m"]
        net_annual = round(gross_rev - TOTAL_OPEX_USD_M_YEAR, 4)

        # Cash flows over plant lifetime (simple flat model — no ramp-up for clarity)
        cash_flows = [net_annual] * PLANT_LIFETIME_YEARS

        npv    = _npv(cash_flows, DISCOUNT_RATE)
        irr    = _irr(TOTAL_CAPEX_USD_M, cash_flows)
        # Simple payback: CapEx / net annual profit
        payback = round(TOTAL_CAPEX_USD_M / net_annual, 1) if net_annual > 0 else float("inf")

        return {
            "total_capex_usd_m"      : round(TOTAL_CAPEX_USD_M, 2),
            "net_annual_profit_usd_m": net_annual,
            "discount_rate"          : DISCOUNT_RATE,
            "plant_lifetime_years"   : PLANT_LIFETIME_YEARS,
            "npv_usd_m"              : npv,
            "irr_pct"                : round(irr * 100, 2),
            "simple_payback_years"   : payback,
            "npv_positive"           : npv > 0,
            "investment_grade"       : "✅ Viable" if npv > 0 and irr > DISCOUNT_RATE else "⚠️ Marginal",
        }

    # ── 5. Scenario Comparison ────────────────────────────────────────────────

    def scenario_comparison(self) -> list:
        """
        Run the full revenue & investment analysis for all three carbon price
        scenarios and return a comparison table.
        """
        results = []
        for scenario, price in CARBON_PRICE_SCENARIOS.items():
            runner = RevenueProjModel(
                capacity_t_day  = self.capacity,
                composition     = self.composition,
                operational_days= self.op_days,
                carbon_scenario = scenario,
            )
            rev     = runner.annual_revenue()
            metrics = runner.investment_metrics()
            results.append({
                "scenario"                  : scenario.upper(),
                "carbon_price_usd_tonne"    : price,
                "gross_revenue_usd_m"       : rev["total_gross_revenue_usd_m"],
                "net_annual_profit_usd_m"   : metrics["net_annual_profit_usd_m"],
                "npv_usd_m"                 : metrics["npv_usd_m"],
                "irr_pct"                   : metrics["irr_pct"],
                "payback_years"             : metrics["simple_payback_years"],
                "investment_grade"          : metrics["investment_grade"],
            })
        return results

    # ── 6. 20-Year Cumulative P&L ─────────────────────────────────────────────

    def cumulative_pl_projection(self, growth_rate: float = 0.03) -> list:
        """
        Year-by-year profit & loss projection over the plant lifetime,
        incorporating waste growth rate and compounding carbon credit volumes.

        Args:
            growth_rate: annual waste intake growth rate (default 3% CAGR)

        Returns:
            List of annual P&L records
        """
        gross_base = self.annual_revenue()["total_gross_revenue_usd_m"]
        records    = []
        cumulative_profit = -TOTAL_CAPEX_USD_M   # start with CapEx outlay

        for yr in range(1, PLANT_LIFETIME_YEARS + 1):
            factor      = (1 + growth_rate) ** (yr - 1)
            gross_rev   = round(gross_base * factor, 4)
            opex        = round(TOTAL_OPEX_USD_M_YEAR * (1 + 0.02) ** (yr - 1), 4)  # 2% OpEx inflation
            net_profit  = round(gross_rev - opex, 4)
            cumulative_profit = round(cumulative_profit + net_profit, 4)

            records.append({
                "year"                    : 2025 + yr,
                "gross_revenue_usd_m"     : gross_rev,
                "opex_usd_m"              : opex,
                "net_profit_usd_m"        : net_profit,
                "cumulative_profit_usd_m" : cumulative_profit,
                "breakeven_reached"       : cumulative_profit >= 0,
                "gross_revenue_inr_cr"    : round(gross_rev * USD_TO_INR * 1e6 / 1e7, 2),
            })
        return records

    # ── 7. Full Report ────────────────────────────────────────────────────────

    def full_report(self) -> dict:
        """
        Return the complete financial projection report.
        """
        return {
            "metadata": {
                "model"           : "ATMOSCHAIN Revenue Projection Model v1.0",
                "plant_location"  : "Proposed site: Ghazipur / NCR, Delhi",
                "capacity_t_day"  : self.capacity,
                "carbon_scenario" : self.carbon_scenario,
                "generated_by"    : "analytics/revenue_projection.py",
            },
            "physical_summary"      : self.physical_summary(),
            "annual_revenue"        : self.annual_revenue(),
            "capex_opex"            : self.capex_opex_summary(),
            "investment_metrics"    : self.investment_metrics(),
            "scenario_comparison"   : self.scenario_comparison(),
            "cumulative_pl_20yr"    : self.cumulative_pl_projection(),
        }


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("=" * 70)
    print("ATMOSCHAIN — Plasma Plant Revenue Projection (500 t/day, BASE scenario)")
    print("=" * 70)

    rp = RevenueProjModel(capacity_t_day=500, carbon_scenario="base")

    print("\n[1] PHYSICAL SUMMARY")
    print(json.dumps(rp.physical_summary(), indent=2))

    print("\n[2] ANNUAL REVENUE BREAKDOWN")
    rev = rp.annual_revenue()
    for k, v in rev.items():
        print(f"  {k:40s}: {v}")

    print("\n[3] CAPEX / OPEX")
    co = rp.capex_opex_summary()
    print(f"  Total CapEx : USD {co['total_capex_usd_m']} M  (₹{co['total_capex_inr_cr']} Cr)")
    print(f"  Total OpEx  : USD {co['total_opex_usd_m_year']} M/year")
    print(f"  Net Profit  : USD {co['net_annual_profit_usd_m']} M/year")
    print(f"  EBITDA Margin: {co['ebitda_margin_pct']}%")

    print("\n[4] INVESTMENT METRICS")
    metrics = rp.investment_metrics()
    print(f"  NPV         : USD {metrics['npv_usd_m']} M")
    print(f"  IRR         : {metrics['irr_pct']}%")
    print(f"  Payback     : {metrics['simple_payback_years']} years")
    print(f"  Grade       : {metrics['investment_grade']}")

    print("\n[5] SCENARIO COMPARISON (Bear / Base / Bull)")
    print(f"  {'Scenario':8} | {'Rev (USD M)':12} | {'Net (USD M)':12} | {'IRR (%)':8} | {'Payback':8}")
    print(f"  {'-'*60}")
    for s in rp.scenario_comparison():
        print(f"  {s['scenario']:8} | {s['gross_revenue_usd_m']:12.3f} | "
              f"{s['net_annual_profit_usd_m']:12.3f} | {s['irr_pct']:8.2f} | "
              f"{s['payback_years']:8.1f}")

    print("\n[6] 20-YEAR CUMULATIVE P&L (first 5 + last year)")
    pl = rp.cumulative_pl_projection()
    for yr_data in (pl[:5] + [pl[-1]]):
        be = "✅ BREAK EVEN" if yr_data["breakeven_reached"] else ""
        print(f"  {yr_data['year']}: Net=USD {yr_data['net_profit_usd_m']:.3f}M | "
              f"Cumulative=USD {yr_data['cumulative_profit_usd_m']:.2f}M {be}")
