# 🌍 Gaia Shield — Predictive Environmental Crime Early Warning

Predicts where illegal mining, logging, and poaching are likely to happen next, and
sends rangers one clear, explainable alert instead of a flood of noise.

This repo is a **working hackathon MVP**: a FastAPI backend that runs a full
Watch → Think → Alert pipeline over a real protected-forest bounding box
(Nilgiri Biosphere Reserve, Western Ghats, India), and a live map dashboard
showing risk zones and explainable alerts in real time.

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | **Python 3.11 + FastAPI + Uvicorn** | Fast to build, async, auto-generated OpenAPI docs at `/docs` |
| Data models | **Pydantic v2** | Type-safe schemas shared by API + pipeline |
| Change detection | **NDVI (Normalized Difference Vegetation Index)** math over a synthetic grid, structured to be swapped for real Sentinel-2 bands | NDVI is the standard remote-sensing signal for vegetation loss |
| Prediction / risk scoring | Custom weighted rule-based model (`prediction_engine.py`) | Fully explainable — every point in the 0–100 score is traceable, which matters for ranger trust and judge Q&A |
| Report generation (Agent 4) | **Anthropic Claude API** (`claude-sonnet-4-6`) with a deterministic template fallback | Turns structured evidence into plain-English alerts; runs with zero setup, upgrades automatically if `ANTHROPIC_API_KEY` is set |
| Frontend | **Vanilla HTML/CSS/JS + Leaflet.js** (via CDN, no build step) | Zero install, opens directly in a browser, easy to demo on stage |
| Map tiles | **CARTO dark basemap** (OpenStreetMap data) | Free, no API key required |
| Data sources it's built to plug into | Sentinel Hub / Copernicus (Sentinel-2), NASA FIRMS, Planet NICFI, OpenStreetMap Overpass API, government license registries | All free/public tier available — see `satellite_engine.py` → `fetch_real_ndvi()` for the exact integration path |

**No paid infrastructure required to run the demo.** The only optional paid
piece is the Claude API call for nicer alert prose, and it degrades
gracefully to a template if you don't set a key.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│  satellite_engine │ --> │  prediction_engine    │ --> │  ai_agents          │
│  (Watch)          │     │  (Think / Score)      │     │  (Explain)          │
│                    │     │                        │     │                     │
│  NDVI grid, roads, │     │  Agent 2: Pattern      │     │  Agent 1: Image     │
│  rivers, history   │     │  Detective + Agent 3:  │     │  Analyst (evidence) │
│                    │     │  Prediction Expert     │     │  Agent 4: Report    │
│                    │     │  → risk_score 0-100    │     │  Writer (plain      │
│                    │     │                        │     │  English alert)     │
└─────────────────┘     └──────────────────────┘     └──────────┬────────┘
                                                                    │
                                                                    v
                                                        ┌─────────────────────┐
                                                        │  FastAPI (main.py)   │
                                                        │  /api/zones           │
                                                        │  /api/alerts           │
                                                        │  /api/simulate         │
                                                        └──────────┬────────────┘
                                                                    │
                                                                    v
                                                    ┌───────────────────────────┐
                                                    │  frontend/index.html        │
                                                    │  Leaflet map + alert feed    │
                                                    └───────────────────────────┘
```

144 grid cells cover the reserve. Each simulated "satellite pass" (`POST
/api/simulate`) advances the clock ~2 days and recomputes NDVI, risk score,
and alerts for every cell — mirroring a real Sentinel-2 revisit cadence.
Three cells are scripted with a slow-building NDVI drop so the demo always
has a clear "incursion story" for judges to watch unfold.

---

## Project structure

```
gaia-shield/
├── backend/
│   ├── main.py               FastAPI app, wires the pipeline, exposes the API
│   ├── satellite_engine.py   Step 1: Watch — NDVI grid + change detection
│   ├── prediction_engine.py  Step 2: Think — risk scoring (Agents 2 & 3)
│   ├── ai_agents.py          Step 3: Explain — evidence + report writer (Agents 1 & 4)
│   ├── models.py             Shared Pydantic schemas
│   └── requirements.txt
└── frontend/
    └── index.html            Live map + alerts dashboard (no build step)
```

---

## Running it

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs auto-generated at **http://localhost:8000/docs**

Optional — enable LLM-written alert explanations:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Frontend

Just open `frontend/index.html` in a browser (double-click it, or serve it:
`python3 -m http.server 5500` from the `frontend/` folder). It talks to the
API at `http://localhost:8000` by default — change `API_BASE` at the top of
the `<script>` block in `index.html` if your backend runs elsewhere.

### 3. Demo flow

1. Dashboard loads showing the reserve with all 144 zones at baseline (day 0).
2. Click **"Run next satellite pass"** a few times.
3. Around day 6–8, watch a risk zone light up amber/red as NDVI drops, and a
   fully explained alert appears in the side panel with confidence %,
   predicted window, and the exact evidence that triggered it.
4. Acknowledge / resolve alerts to simulate a ranger workflow.

---

## Key API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Simulated day, zone count |
| GET | `/api/zones` | All 144 zones with current NDVI + risk score |
| GET | `/api/alerts?status=open` | All generated alerts, optionally filtered |
| POST | `/api/simulate` | Advance one satellite pass, run the full pipeline |
| POST | `/api/alerts/{id}/acknowledge` | Ranger acknowledges an alert |
| POST | `/api/alerts/{id}/resolve` | Ranger marks an alert resolved |
| POST | `/api/reset` | Reset simulation to day 0 |

---

## How the risk score works (fully explainable, no black box)

```
risk_score = 45 × ndvi_drop_component
           + 15 × road_proximity_component
           + 10 × river_proximity_component
           + 20 × historical_incident_component
           + 10 × seasonality_component
```

Every weight and component is a plain float you can inspect and tune in
`prediction_engine.py` — deliberately not a black-box ML model, so it can be
explained to a ranger, a judge, or a regulator in one sentence.

## Going from demo to production

1. **Real imagery**: implement `fetch_real_ndvi()` in `satellite_engine.py`
   using Sentinel Hub's free tier (Sentinel-2 L2A, 10m resolution, 2–5 day
   revisit). The rest of the pipeline needs zero changes since it only
   depends on the `Zone` schema.
2. **Real roads/rivers/boundaries**: replace the synthetic road/river cells
   with an OpenStreetMap Overpass API query for the AOI.
3. **Persistence**: swap the in-memory `STATE` dict in `main.py` for
   Postgres + PostGIS (great fit since everything is already geo-tagged).
4. **Notifications**: hook `_run_pipeline()`'s new-alert loop into SMS
   (Twilio) or push notifications for offline-capable ranger phones.
5. **Historical incidents**: replace the synthetic `history` counts with a
   real incident database (park authority records).
