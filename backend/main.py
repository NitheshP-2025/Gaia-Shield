"""
Gaia Shield - Backend API
==========================
FastAPI app that runs the full pipeline end to end:

  SatelliteEngine (watch)  ->  prediction_engine (think/score)
       -> ai_agents (explain)  ->  Alert objects  -> in-memory store

Run:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Then open frontend/index.html (or serve it) and it will call this API
at http://localhost:8000
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import Zone, Alert, SimulateResponse
from satellite_engine import SatelliteEngine
from prediction_engine import score_all_zones, predicted_window_days, confidence_from_signals
from ai_agents import image_analyst_notes, report_writer

app = FastAPI(title="Gaia Shield API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SatelliteEngine()

# --- in-memory "database" (swap for Postgres/SQLite in production) ---
STATE = {
    "current_day": 0,
    "zones": [],          # List[Zone] latest scored snapshot
    "alerts": [],          # List[Alert] all-time
}

RISK_ALERT_THRESHOLD = 65  # zones scoring at/above this generate an alert


def _run_pipeline(day: int) -> List[Alert]:
    zones = engine.get_zones(day)
    zones = score_all_zones(zones, day)
    STATE["zones"] = zones
    STATE["current_day"] = day

    already_alerted_zone_ids = {a.zone_id for a in STATE["alerts"] if a.status == "open"}
    new_alerts = []

    for zone in zones:
        if zone.risk_score >= RISK_ALERT_THRESHOLD and zone.id not in already_alerted_zone_ids:
            threat_type = engine.scripted_threat_type(zone.id)
            confidence = confidence_from_signals(zone)
            window = predicted_window_days(zone.risk_score)
            evidence = image_analyst_notes(zone)
            explanation = report_writer(zone, threat_type, confidence, window, evidence)

            alert = Alert(
                id=str(uuid.uuid4())[:8],
                zone_id=zone.id,
                lat=zone.lat,
                lon=zone.lon,
                threat_type=threat_type,
                confidence=confidence,
                predicted_window_days=window,
                headline=f"{threat_type.replace('_', ' ').title()} predicted - {confidence}% confidence",
                explanation=explanation,
                evidence=evidence,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            new_alerts.append(alert)
            STATE["alerts"].append(alert)

    return new_alerts


# Seed baseline (day 0) at startup so /zones and /alerts have data immediately
_run_pipeline(0)


@app.get("/api/health")
def health():
    return {"status": "ok", "day": STATE["current_day"], "zones_monitored": len(STATE["zones"])}


@app.get("/api/zones", response_model=List[Zone])
def get_zones():
    return STATE["zones"]


@app.get("/api/alerts", response_model=List[Alert])
def get_alerts(status: str = None):
    if status:
        return [a for a in STATE["alerts"] if a.status == status]
    return STATE["alerts"]


@app.post("/api/alerts/{alert_id}/acknowledge", response_model=Alert)
def acknowledge_alert(alert_id: str):
    for a in STATE["alerts"]:
        if a.id == alert_id:
            a.status = "acknowledged"
            return a
    raise HTTPException(status_code=404, detail="Alert not found")


@app.post("/api/alerts/{alert_id}/resolve", response_model=Alert)
def resolve_alert(alert_id: str):
    for a in STATE["alerts"]:
        if a.id == alert_id:
            a.status = "resolved"
            return a
    raise HTTPException(status_code=404, detail="Alert not found")


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate_next_pass():
    """Advances the simulated satellite clock by one pass (~2-5 real days)
    and re-runs the full Watch -> Think -> Alert pipeline. This is the
    button a judge clicks to watch the system 'discover' a new threat."""
    next_day = STATE["current_day"] + 2
    new_alerts = _run_pipeline(next_day)
    return SimulateResponse(
        day=next_day,
        zones_scanned=len(STATE["zones"]),
        new_alerts=new_alerts,
        total_open_alerts=len([a for a in STATE["alerts"] if a.status == "open"]),
    )


@app.post("/api/reset")
def reset():
    STATE["alerts"] = []
    _run_pipeline(0)
    return {"status": "reset", "day": 0}
