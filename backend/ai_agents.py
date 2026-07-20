"""
Gaia Shield - AI Agents
========================
"Agent 1: Image Analyst" and "Agent 4: Report Writer" from the project
brief. Agent 2 (Pattern Detective) and Agent 3 (Prediction Expert) live in
prediction_engine.py since their output is numeric/structured rather than
prose.

Report Writer works in two modes:
  - LLM mode: if ANTHROPIC_API_KEY is set, calls Claude (claude-sonnet-4-6)
    to turn the structured evidence into a natural, ranger-readable
    explanation.
  - Template mode (default, no key required): deterministic, still reads
    naturally, and is what keeps this demo runnable with zero setup.
"""
import os
from typing import List
from models import Zone, Evidence

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


def image_analyst_notes(zone: Zone) -> List[Evidence]:
    """Agent 1: turns raw NDVI + geo signals into human-readable evidence
    lines, the way an analyst would annotate a satellite image."""
    ev = []
    if zone.ndvi_drop > 0.03:
        pct = round(zone.ndvi_drop * 100, 1)
        ev.append(Evidence(
            label="Vegetation loss detected",
            detail=f"NDVI dropped {pct}% vs. baseline ({zone.ndvi_baseline} -> {zone.ndvi_current}), "
                   f"consistent with active land clearing.",
        ))
    if zone.near_road:
        ev.append(Evidence(
            label="Access route present",
            detail="Zone sits on or adjacent to a known road corridor, enabling equipment/vehicle access.",
        ))
    if zone.distance_to_river_km < 5:
        ev.append(Evidence(
            label="Near waterway",
            detail=f"Only {zone.distance_to_river_km} km from the nearest river - typical siting for gold panning/mining runoff.",
        ))
    if zone.historical_incidents >= 2:
        ev.append(Evidence(
            label="Repeat-offense geography",
            detail=f"{zone.historical_incidents} prior recorded incidents within this cell in past monitoring cycles.",
        ))
    if not ev:
        ev.append(Evidence(
            label="Stable",
            detail="No significant anomaly - vegetation and access indicators within normal range.",
        ))
    return ev


def _template_report(zone: Zone, threat_type: str, confidence: float, window_days: int, evidence: List[Evidence]) -> str:
    threat_label = threat_type.replace("_", " ")
    reasons = "; ".join(f"{e.label.lower()}" for e in evidence if e.label != "Stable")
    return (
        f"{threat_label.capitalize()} is predicted at this location with {confidence}% confidence, "
        f"expected within the next {window_days} days. This assessment is based on: {reasons}. "
        f"Recommend prioritized ranger patrol coverage for this zone during the predicted window."
    )


def _llm_report(zone: Zone, threat_type: str, confidence: float, window_days: int, evidence: List[Evidence]) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    evidence_text = "\n".join(f"- {e.label}: {e.detail}" for e in evidence)
    prompt = (
        "You are the 'Report Writer' agent in an environmental-crime early-warning system. "
        "Write a SHORT (2-3 sentence) alert explanation for a field ranger, in plain, direct language. "
        "No preamble, no markdown, just the explanation text.\n\n"
        f"Threat type: {threat_type.replace('_', ' ')}\n"
        f"Confidence: {confidence}%\n"
        f"Predicted window: {window_days} days\n"
        f"Risk score: {zone.risk_score}/100\n"
        f"Evidence:\n{evidence_text}\n"
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if hasattr(block, "text")).strip()


def report_writer(zone: Zone, threat_type: str, confidence: float, window_days: int, evidence: List[Evidence]) -> str:
    """Agent 4: Report Writer - produces the human-facing explanation.
    Falls back to the template automatically if no API key / package / call fails,
    so the demo never breaks mid-presentation."""
    if _ANTHROPIC_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _llm_report(zone, threat_type, confidence, window_days, evidence)
        except Exception:
            pass
    return _template_report(zone, threat_type, confidence, window_days, evidence)
