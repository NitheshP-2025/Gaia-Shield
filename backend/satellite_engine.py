"""
Gaia Shield - Satellite Engine
==============================
Responsible for STEP 1 (Watch) in the pipeline: turning raw satellite /
open-map data into a grid of monitored "zones" with an NDVI (Normalized
Difference Vegetation Index) reading for each one.

DEMO MODE vs PRODUCTION MODE
-----------------------------
Real deployments would pull imagery from:
  - Sentinel Hub / Copernicus (ESA)  -> Sentinel-2 L2A bands (B04 red, B08 NIR)
  - NASA FIRMS                        -> active fire / thermal anomalies
  - Planet NICFI                      -> high-res tropical forest basemaps
  - OpenStreetMap Overpass API        -> roads, rivers, settlements, park boundaries

Those all require API keys and outbound network access that a hackathon
sandbox usually doesn't have configured yet, so this module ships a
SYNTHETIC-BUT-REALISTIC data generator: a fixed grid of cells over a real
protected-forest bounding box, with deterministic pseudo-random NDVI decay
and a couple of "scripted" zones that clearly simulate a mining/logging
incursion over time so the prediction pipeline has something real to catch.

Swap `SatelliteEngine.get_zones()` for a real Sentinel Hub call (see
`fetch_real_ndvi()` stub below) when you have API credentials - nothing
downstream needs to change because it only depends on the Zone schema.
"""
import hashlib
import math
import random
from typing import List

from models import Zone

# Bounding box: Nilgiri Biosphere Reserve area, Western Ghats, India
# (a real UNESCO-listed protected forest -- swap for any AOI you like)
LAT_MIN, LAT_MAX = 11.30, 11.55
LON_MIN, LON_MAX = 76.55, 76.85
GRID_SIZE = 12  # 12x12 = 144 monitored cells

# A handful of cells are "scripted" to simulate an active incursion so the
# demo always has a clear, explainable story to show judges.
SCRIPTED_INCURSIONS = [
    {"row": 4, "col": 7, "onset_day": 2, "rate": 0.09, "type": "illegal_mining"},
    {"row": 8, "col": 3, "onset_day": 4, "rate": 0.06, "type": "illegal_logging"},
    {"row": 2, "col": 9, "onset_day": 6, "rate": 0.05, "type": "poaching_risk"},
]


def _seeded_random(zone_id: str, salt: str = "") -> float:
    """Deterministic pseudo-random float in [0,1) from a zone id."""
    h = hashlib.sha256(f"{zone_id}-{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class SatelliteEngine:
    def __init__(self):
        self.rows = GRID_SIZE
        self.cols = GRID_SIZE
        self._build_static_layers()

    def _build_static_layers(self):
        """Static OSM-style layers: roads, rivers, historical incident counts."""
        self.road_cells = set()
        self.river_cells = set()
        self.history = {}

        for r in range(self.rows):
            for c in range(self.cols):
                zid = f"z-{r}-{c}"
                # A diagonal "river" and a horizontal "road" through the reserve
                if abs(r - c) <= 0:
                    self.river_cells.add(zid)
                if r == 5 or r == 6:
                    self.road_cells.add(zid)
                # Historical incident density, higher near river+road crossings
                base = 1 if (zid in self.road_cells and zid in self.river_cells) else 0
                self.history[zid] = base + int(_seeded_random(zid, "hist") * 3)

    def _cell_latlon(self, r: int, c: int):
        lat = LAT_MIN + (LAT_MAX - LAT_MIN) * (r / (self.rows - 1))
        lon = LON_MIN + (LON_MAX - LON_MIN) * (c / (self.cols - 1))
        return round(lat, 5), round(lon, 5)

    def _distance_to_nearest_river_km(self, r: int, c: int) -> float:
        best = 999.0
        for river_id in self.river_cells:
            rr, rc = map(int, river_id.split("-")[1:])
            d = math.hypot(r - rr, c - rc)
            best = min(best, d)
        # rough conversion: 1 grid cell ~= 2.7km at this grid resolution
        return round(best * 2.7, 2)

    def get_zones(self, day: int) -> List[Zone]:
        """
        Returns the current state of every monitored zone as of `day`
        (day 0 = baseline satellite pass, increasing day = later passes).
        This is where a production system would instead compute NDVI from
        real Sentinel-2 band math: NDVI = (NIR - RED) / (NIR + RED)
        """
        zones = []
        for r in range(self.rows):
            for c in range(self.cols):
                zid = f"z-{r}-{c}"
                lat, lon = self._cell_latlon(r, c)

                baseline_ndvi = 0.62 + 0.25 * _seeded_random(zid, "base")
                natural_noise = (_seeded_random(zid, f"noise-{day}") - 0.5) * 0.02

                drop = natural_noise
                for inc in SCRIPTED_INCURSIONS:
                    if r == inc["row"] and c == inc["col"] and day >= inc["onset_day"]:
                        days_active = day - inc["onset_day"]
                        drop += inc["rate"] * days_active

                current_ndvi = max(0.05, baseline_ndvi - drop)
                ndvi_drop = max(0.0, round((baseline_ndvi - current_ndvi) / baseline_ndvi, 4))

                zones.append(Zone(
                    id=zid,
                    lat=lat,
                    lon=lon,
                    ndvi_current=round(current_ndvi, 4),
                    ndvi_baseline=round(baseline_ndvi, 4),
                    ndvi_drop=ndvi_drop,
                    near_road=zid in self.road_cells,
                    near_river=zid in self.river_cells,
                    distance_to_river_km=self._distance_to_nearest_river_km(r, c),
                    historical_incidents=self.history[zid],
                    risk_score=0.0,     # filled in by prediction_engine
                    risk_band="low",
                ))
        return zones

    def scripted_threat_type(self, zone_id: str) -> str:
        r, c = map(int, zone_id.split("-")[1:])
        for inc in SCRIPTED_INCURSIONS:
            if inc["row"] == r and inc["col"] == c:
                return inc["type"]
        return "illegal_logging"


def fetch_real_ndvi(bbox, date_from, date_to, sentinelhub_client_id, sentinelhub_client_secret):
    """
    STUB for production use. To go live:
      1. pip install sentinelhub
      2. Create a free Sentinel Hub account -> get client id/secret
      3. Request Sentinel-2 L2A B04 (red) and B08 (NIR) for `bbox`
      4. NDVI = (B08 - B04) / (B08 + B04) per pixel, aggregate per grid cell
      5. Return the same list-of-Zone shape get_zones() returns above,
         so nothing else in the pipeline needs to change.
    """
    raise NotImplementedError(
        "Plug in Sentinel Hub / Planet credentials here for production use. "
        "See docstring for the 5-step integration path."
    )
