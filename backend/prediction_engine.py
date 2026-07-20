"""
Gaia Shield - Prediction Engine
================================
STEP 2 (Think) of the pipeline. Implements "Agent 2: Pattern Detective"
and "Agent 3: Prediction Expert" as an explainable, weighted risk model
(no black-box needed for a hackathon judge to trust the output - every
number below is traceable to a reason).

Risk score (0-100) = weighted sum of:
  - NDVI drop magnitude      (is vegetation actually disappearing?)
  - Road proximity           (new/existing access route in or near the cell)
  - River proximity          (miners & loggers cluster near water)
  - Historical incident count (repeat-offender geography)
  - Seasonality              (dry-season / post-monsoon = high activity season)

Each factor is capped and weighted, then combined. Confidence is derived
from how many independent signals agree (more corroborating evidence =
higher confidence, mirroring how a real analyst would reason).
"""
from datetime import date
from typing import List
from models import Zone

WEIGHTS = {
    "ndvi": 45,
    "road": 15,
    "river": 10,
    "history": 20,
    "season": 10,
}

RISK_THRESHOLDS = {
    "low": 0,
    "medium": 40,
    "high": 65,
    "critical": 85,
}


def _season_score(simulated_day: int) -> float:
    """
    Toy seasonality curve: risk rises as the monsoon ends (illegal mining
    typically spikes once rivers recede and forest floor is accessible).
    day % 30 used to fake an annual cycle compressed for a demo.
    """
    cycle_pos = simulated_day % 30
    # Peaks mid-cycle (post-monsoon analogue), troughs at cycle start (peak monsoon)
    return 0.3 + 0.7 * abs((cycle_pos / 30) - 0.5) * 2


def _history_score(incident_count: int) -> float:
    return min(1.0, incident_count / 4.0)


def score_zone(zone: Zone, simulated_day: int) -> Zone:
    ndvi_component = min(1.0, zone.ndvi_drop * 3.0)          # a 33%+ drop maxes this out
    road_component = 1.0 if zone.near_road else 0.15
    river_component = max(0.0, 1.0 - (zone.distance_to_river_km / 15.0))
    history_component = _history_score(zone.historical_incidents)
    season_component = _season_score(simulated_day)

    raw = (
        ndvi_component * WEIGHTS["ndvi"]
        + road_component * WEIGHTS["road"]
        + river_component * WEIGHTS["river"]
        + history_component * WEIGHTS["history"]
        + season_component * WEIGHTS["season"]
    )
    risk = round(min(100.0, raw), 1)

    if risk >= RISK_THRESHOLDS["critical"]:
        band = "critical"
    elif risk >= RISK_THRESHOLDS["high"]:
        band = "high"
    elif risk >= RISK_THRESHOLDS["medium"]:
        band = "medium"
    else:
        band = "low"

    zone.risk_score = risk
    zone.risk_band = band
    return zone


def score_all_zones(zones: List[Zone], simulated_day: int) -> List[Zone]:
    return [score_zone(z, simulated_day) for z in zones]


def predicted_window_days(risk_score: float) -> int:
    """Agent 3: Prediction Expert - higher risk implies a shorter runway
    before activity is expected to start (inverse relationship)."""
    if risk_score >= 90:
        return 3
    if risk_score >= 80:
        return 7
    if risk_score >= 65:
        return 14
    return 21


def confidence_from_signals(zone: Zone) -> float:
    """More corroborating signals -> higher confidence, capped at 97
    (we never claim certainty)."""
    signals = 0
    if zone.ndvi_drop > 0.05:
        signals += 1
    if zone.near_road:
        signals += 1
    if zone.near_river or zone.distance_to_river_km < 5:
        signals += 1
    if zone.historical_incidents >= 2:
        signals += 1

    base = 45 + signals * 13
    # nudge by raw risk score so stronger NDVI anomalies read as more confident
    base += (zone.risk_score - 50) * 0.15
    return round(max(30.0, min(97.0, base)), 1)
