"""
ATMOSCHAIN — Analytics Module
environmental_impact_model.py

Ghazipur Landfill Environmental Impact & Heatmap Analysis.

Provides:
  - Radial methane dispersion zones around Ghazipur landfill
  - Air Quality Index (AQI) estimation from CH4 & particulate emissions
  - Population health risk tier mapping across affected wards
  - CO₂-equivalent impact comparison: landfill vs. plasma gasification
  - City-wide avoided emissions summary for Delhi-NCR

Data sources:
  - CPCB Annual Report on Solid Waste Management (2023)
  - IPCC AR6 GWP-100 for CH4 (GWP = 28)
  - Ghazipur waste receipt: ~2,800 tonnes/day (EDMC 2024)
  - WHO AQI thresholds and SAFAR (System of Air Quality & Weather Forecasting) India

Author: ATMOSCHAIN Dev Team
"""

import math
from typing import Optional


# ─── Ghazipur Landfill Baseline Data ─────────────────────────────────────────

GHAZIPUR_COORDS = {
    "lat": 28.6271,
    "lon": 77.3232,
    "address": "Ghazipur, East Delhi, Delhi – 110096",
}

# Waste intake per day (EDMC data, tonnes)
DAILY_WASTE_TONNES = 2800.0

# Waste composition (CPCB India SWM Report fractions)
GHAZIPUR_COMPOSITION = {
    "organic":  0.50,   # food & garden waste
    "paper":    0.12,
    "plastic":  0.10,
    "textile":  0.06,
    "metal":    0.02,
    "glass":    0.02,
    "inert":    0.08,   # ash, dust, construction debris
    "mixed":    0.10,
}

# DOC values (IPCC Table 3.4)
DOC_BY_WASTE_TYPE = {
    "plastic": 0.00, "organic": 0.15, "paper": 0.40,
    "textile": 0.24, "wood": 0.43,   "metal": 0.00,
    "glass":   0.00, "inert": 0.00,  "mixed": 0.12,
    "unknown": 0.10,
}
DOCf   = 0.50
F      = 0.50
MCF    = 1.00
GWP100 = 28
MOLAR  = 16.0 / 12.0

# Landfill area (ha) and height (m) — Ghazipur reality
LANDFILL_AREA_HA   = 28.0
LANDFILL_HEIGHT_M  = 65.0   # dangerously above 20m permitted limit

# Average annual wind speed (m/s) for Delhi (IMD data)
WIND_SPEED_MS = 3.2

# Population in surrounding wards (EDMC Ward census estimates)
AFFECTED_WARDS = [
    {"ward": "Ghazipur",          "population": 85_000,  "distance_km": 0.5},
    {"ward": "Kondli",            "population": 120_000, "distance_km": 1.2},
    {"ward": "Patparganj",        "population": 105_000, "distance_km": 2.1},
    {"ward": "Mayur Vihar III",   "population": 98_000,  "distance_km": 3.0},
    {"ward": "Trilokpuri",        "population": 135_000, "distance_km": 3.8},
    {"ward": "Laxmi Nagar",       "population": 160_000, "distance_km": 5.0},
]

# PM2.5 emission factor from landfill (µg/m³/km at 1-km radius, empirical)
PM25_EMISSION_FACTOR = 120.0   # µg/m³ at 1 km from source

# WHO AQI PM2.5 thresholds (µg/m³, 24-hr average)
AQI_THRESHOLDS = [
    (0,   12,    "Good",        "green"),
    (12,  35.4,  "Moderate",   "yellow"),
    (35.4,55.4,  "Unhealthy for Sensitive Groups", "orange"),
    (55.4,150.4, "Unhealthy",  "red"),
    (150.4,250.4,"Very Unhealthy","purple"),
    (250.4,500,  "Hazardous",  "maroon"),
]

# Plasma gasification efficiency assumption (eliminates 97% of methane)
PLASMA_METHANE_ELIMINATION_RATE = 0.97


# ─── Core Computation Functions ───────────────────────────────────────────────

def _calculate_daily_ch4(
    composition: dict,
    total_tonnes_per_day: float
) -> dict:
    """
    Compute daily methane generation from a landfill intake using
    the IPCC First-Order Decay formula.

    Returns:
        dict with ch4_kg_per_day, co2e_tonnes_per_day
    """
    total_ch4_kg    = 0.0
    total_co2e_t    = 0.0

    for waste_class, fraction in composition.items():
        mass_kg      = fraction * total_tonnes_per_day * 1000.0
        mass_t       = mass_kg / 1000.0
        doc          = DOC_BY_WASTE_TYPE.get(waste_class, 0.10)
        ch4_t        = mass_t * doc * DOCf * F * MCF * MOLAR
        ch4_kg       = ch4_t * 1000.0
        co2e_t       = ch4_t * GWP100
        total_ch4_kg += ch4_kg
        total_co2e_t += co2e_t

    return {
        "ch4_kg_per_day":     round(total_ch4_kg, 2),
        "ch4_tonnes_per_day": round(total_ch4_kg / 1000.0, 4),
        "co2e_tonnes_per_day":round(total_co2e_t, 4),
        "co2e_kg_per_day":    round(total_co2e_t * 1000.0, 2),
    }


def _pm25_at_distance(distance_km: float) -> float:
    """
    Estimate PM2.5 concentration (µg/m³) at a given distance from landfill
    using an inverse-square Gaussian dispersion approximation.

    Args:
        distance_km: radial distance from Ghazipur landfill (km)

    Returns:
        PM2.5 concentration in µg/m³
    """
    if distance_km <= 0:
        distance_km = 0.1
    # Gaussian dispersion: concentration ∝ 1 / (distance²)
    pm25 = PM25_EMISSION_FACTOR / (distance_km ** 2)
    return round(min(pm25, 500.0), 2)   # cap at AQI hazardous ceiling


def _get_aqi_band(pm25: float) -> dict:
    """Map PM2.5 value to AQI band label and color."""
    for lo, hi, label, color in AQI_THRESHOLDS:
        if lo <= pm25 < hi:
            return {"label": label, "color": color, "pm25": pm25}
    return {"label": "Hazardous", "color": "maroon", "pm25": pm25}


def _health_risk_tier(pm25: float) -> str:
    """Return population health risk tier string."""
    if pm25 < 12:
        return "Minimal"
    elif pm25 < 35.4:
        return "Low"
    elif pm25 < 55.4:
        return "Moderate — Respiratory alerts for sensitive groups"
    elif pm25 < 150.4:
        return "High — Increased hospitalisation risk"
    elif pm25 < 250.4:
        return "Severe — Emergency health advisory"
    else:
        return "Catastrophic — Immediate evacuation recommended"


# ─── Main Model Class ─────────────────────────────────────────────────────────

class EnvironmentalImpactModel:
    """
    Ghazipur Landfill Environmental Impact & Heatmap Model.

    Computes:
      1. Daily methane / CO₂e emission baseline
      2. Radial dispersion heatmap zones (0.5 km to 10 km)
      3. Ward-level AQI & population health risk
      4. Impact delta: landfill vs. ATMOSCHAIN plasma gasification
      5. City-wide avoided emissions projection (10-year)

    Usage:
        model = EnvironmentalImpactModel()
        report = model.full_report()
    """

    def __init__(
        self,
        composition: Optional[dict] = None,
        daily_tonnes: float = DAILY_WASTE_TONNES
    ):
        self.composition  = composition or GHAZIPUR_COMPOSITION
        self.daily_tonnes = daily_tonnes
        self._baseline    = _calculate_daily_ch4(self.composition, self.daily_tonnes)

    # ── 1. Emission Baseline ──────────────────────────────────────────────────

    def emission_baseline(self) -> dict:
        """
        Return the daily & annual methane + CO₂e emission baseline for
        Ghazipur landfill under current open-dumping conditions.
        """
        b = self._baseline
        return {
            "site"                    : "Ghazipur Landfill, East Delhi",
            "daily_waste_intake_t"    : self.daily_tonnes,
            "ch4_kg_per_day"          : b["ch4_kg_per_day"],
            "ch4_tonnes_per_day"      : b["ch4_tonnes_per_day"],
            "ch4_tonnes_per_year"     : round(b["ch4_tonnes_per_day"] * 365, 2),
            "co2e_tonnes_per_day"     : b["co2e_tonnes_per_day"],
            "co2e_tonnes_per_year"    : round(b["co2e_tonnes_per_day"] * 365, 2),
            "co2e_kg_per_day"         : b["co2e_kg_per_day"],
            "landfill_area_ha"        : LANDFILL_AREA_HA,
            "landfill_height_m"       : LANDFILL_HEIGHT_M,
            "gwp_factor_used"         : GWP100,
            "reference_model"         : "IPCC FOD — 2006 Guidelines Vol. 5 Ch. 3",
        }

    # ── 2. Radial Heatmap Zones ───────────────────────────────────────────────

    def radial_heatmap(self, radii_km: Optional[list] = None) -> list:
        """
        Compute PM2.5 concentration and AQI band at concentric radii
        from the Ghazipur landfill centre.

        Args:
            radii_km: list of distances (km) to evaluate (default: 0.5 – 10 km)

        Returns:
            List of dicts, one per radius, with AQI band and health risk tier.
        """
        if radii_km is None:
            radii_km = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0]

        zones = []
        for r in radii_km:
            pm25 = _pm25_at_distance(r)
            aqi  = _get_aqi_band(pm25)
            zones.append({
                "radius_km"   : r,
                "pm25_ugm3"   : pm25,
                "aqi_label"   : aqi["label"],
                "aqi_color"   : aqi["color"],
                "health_risk" : _health_risk_tier(pm25),
                # Approx. lat/lon offset (due East by default for visualisation)
                "approx_lat"  : round(GHAZIPUR_COORDS["lat"], 6),
                "approx_lon"  : round(GHAZIPUR_COORDS["lon"] + r / 111.32, 6),
            })
        return zones

    # ── 3. Ward-Level Health Exposure ────────────────────────────────────────

    def ward_exposure_analysis(self) -> list:
        """
        For each affected ward, compute PM2.5 exposure, AQI band,
        estimated population at risk, and respiratory case estimates.

        Returns:
            List of ward exposure records.
        """
        results = []
        for ward in AFFECTED_WARDS:
            d     = ward["distance_km"]
            pm25  = _pm25_at_distance(d)
            aqi   = _get_aqi_band(pm25)
            risk  = _health_risk_tier(pm25)
            pop   = ward["population"]

            # WHO estimates: 5% of population shows acute symptoms per 10 µg/m³ over safe limit
            excess_pm25  = max(0, pm25 - 12.0)
            symptom_pct  = min(50.0, round(excess_pm25 / 10.0 * 5.0, 1))
            at_risk_pop  = round(pop * symptom_pct / 100)

            results.append({
                "ward"                : ward["ward"],
                "distance_km"         : d,
                "population"          : pop,
                "pm25_ugm3"           : pm25,
                "aqi_label"           : aqi["label"],
                "aqi_color"           : aqi["color"],
                "health_risk_tier"    : risk,
                "symptom_exposure_pct": symptom_pct,
                "estimated_at_risk"   : at_risk_pop,
            })
        return results

    # ── 4. Plasma vs. Landfill Impact Delta ──────────────────────────────────

    def plasma_vs_landfill_delta(self) -> dict:
        """
        Compute the environmental impact difference if ALL Ghazipur waste
        were redirected to an ATMOSCHAIN Plasma Gasification plant instead
        of being open-dumped.

        Returns:
            Dict with avoided CH4, CO₂e, energy generated, and health metric
            improvements.
        """
        b = self._baseline

        # Methane avoidance
        ch4_avoided_kg_day  = b["ch4_kg_per_day"] * PLASMA_METHANE_ELIMINATION_RATE
        co2e_avoided_t_day  = b["co2e_tonnes_per_day"] * PLASMA_METHANE_ELIMINATION_RATE
        co2e_avoided_t_year = round(co2e_avoided_t_day * 365, 2)

        # Energy generation estimate (mixed waste: 600 kWh/tonne net)
        kwh_per_day   = self.daily_tonnes * 600.0
        kwh_per_year  = round(kwh_per_day * 365, 0)
        homes_powered = round(kwh_per_day / 100.0)   # 100 kWh/month/household

        # Carbon-credit value of avoided CO₂e (mid price $20/tonne)
        credits_per_year = co2e_avoided_t_year
        revenue_usd_year = round(credits_per_year * 20.0, 2)
        revenue_inr_year = round(revenue_usd_year * 83.5, 2)

        # AQI improvement at 1-km radius
        pm25_landfill = _pm25_at_distance(1.0)
        pm25_plasma   = round(pm25_landfill * (1 - PLASMA_METHANE_ELIMINATION_RATE), 2)

        return {
            "scenario_current"          : "Open landfill (Ghazipur status quo)",
            "scenario_proposed"         : "ATMOSCHAIN Plasma Gasification plant",
            "ch4_avoided_kg_per_day"    : round(ch4_avoided_kg_day, 2),
            "co2e_avoided_t_per_day"    : round(co2e_avoided_t_day, 4),
            "co2e_avoided_t_per_year"   : co2e_avoided_t_year,
            "electricity_kwh_per_day"   : round(kwh_per_day, 0),
            "electricity_kwh_per_year"  : kwh_per_year,
            "homes_powered_per_day"     : homes_powered,
            "carbon_credits_per_year"   : round(credits_per_year, 2),
            "carbon_revenue_usd_year"   : revenue_usd_year,
            "carbon_revenue_inr_year"   : revenue_inr_year,
            "pm25_at_1km_landfill"      : pm25_landfill,
            "pm25_at_1km_plasma"        : pm25_plasma,
            "aqi_improvement_at_1km"    : {
                "before": _get_aqi_band(pm25_landfill)["label"],
                "after":  _get_aqi_band(pm25_plasma)["label"],
            },
            "methane_elimination_rate_pct": PLASMA_METHANE_ELIMINATION_RATE * 100,
        }

    # ── 5. 10-Year Projection ─────────────────────────────────────────────────

    def ten_year_projection(self, growth_rate: float = 0.03) -> list:
        """
        Project avoided CO₂e and electricity revenue over 10 years,
        accounting for Delhi's waste growth rate.

        Args:
            growth_rate: annual waste growth rate (default 3% CAGR)

        Returns:
            List of yearly projection dicts
        """
        delta   = self.plasma_vs_landfill_delta()
        base_co2e  = delta["co2e_avoided_t_per_year"]
        base_kwh   = delta["electricity_kwh_per_year"]
        base_rev   = delta["carbon_revenue_usd_year"]

        projections = []
        for yr in range(1, 11):
            factor = (1 + growth_rate) ** (yr - 1)
            projections.append({
                "year"                      : 2025 + yr,
                "waste_tonnes_per_day"      : round(self.daily_tonnes * factor, 1),
                "co2e_avoided_tonnes"       : round(base_co2e * factor, 2),
                "electricity_kwh"           : round(base_kwh * factor, 0),
                "carbon_revenue_usd"        : round(base_rev * factor, 2),
                "carbon_revenue_inr"        : round(base_rev * factor * 83.5, 2),
                "trees_equivalent"          : round(base_co2e * factor * 40),
                "cars_off_road_equivalent"  : round(base_co2e * factor / 4.6),
            })
        return projections

    # ── 6. Full Report ────────────────────────────────────────────────────────

    def full_report(self) -> dict:
        """
        Return the complete environmental impact report combining all sub-models.
        """
        return {
            "metadata": {
                "model"       : "ATMOSCHAIN Environmental Impact Model v1.0",
                "site"        : "Ghazipur Landfill, East Delhi",
                "coordinates" : GHAZIPUR_COORDS,
                "generated_by": "analytics/environmental_impact_model.py",
            },
            "emission_baseline"     : self.emission_baseline(),
            "radial_heatmap_zones"  : self.radial_heatmap(),
            "ward_exposure_analysis": self.ward_exposure_analysis(),
            "plasma_vs_landfill"    : self.plasma_vs_landfill_delta(),
            "ten_year_projection"   : self.ten_year_projection(),
        }


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    model = EnvironmentalImpactModel()

    print("=" * 70)
    print("ATMOSCHAIN — Ghazipur Landfill Environmental Impact Report")
    print("=" * 70)

    print("\n[1] EMISSION BASELINE")
    print(json.dumps(model.emission_baseline(), indent=2))

    print("\n[2] RADIAL HEATMAP ZONES (0.5 km → 10 km)")
    for zone in model.radial_heatmap():
        print(f"  {zone['radius_km']} km → PM2.5: {zone['pm25_ugm3']} µg/m³"
              f" | AQI: {zone['aqi_label']} ({zone['aqi_color']})"
              f" | Risk: {zone['health_risk']}")

    print("\n[3] WARD EXPOSURE ANALYSIS")
    for w in model.ward_exposure_analysis():
        print(f"  {w['ward']:22s} | {w['distance_km']} km | "
              f"PM2.5={w['pm25_ugm3']:6.1f} | AQI: {w['aqi_label']:35s} | "
              f"At risk: {w['estimated_at_risk']:,}")

    print("\n[4] PLASMA vs LANDFILL DELTA")
    delta = model.plasma_vs_landfill_delta()
    print(f"  CO₂e avoided/year : {delta['co2e_avoided_t_per_year']:,.2f} tonnes")
    print(f"  Electricity/year  : {delta['electricity_kwh_per_year']:,.0f} kWh")
    print(f"  Carbon revenue/yr : USD {delta['carbon_revenue_usd_year']:,.2f}")
    print(f"  AQI @ 1km: {delta['aqi_improvement_at_1km']['before']} → {delta['aqi_improvement_at_1km']['after']}")

    print("\n[5] 10-YEAR PROJECTION")
    for yr in model.ten_year_projection():
        print(f"  {yr['year']}: CO₂e avoided={yr['co2e_avoided_tonnes']:,.0f}t | "
              f"Revenue=₹{yr['carbon_revenue_inr']:,.0f}")
