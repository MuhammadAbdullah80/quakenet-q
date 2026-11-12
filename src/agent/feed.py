"""The trigger: the USGS real-time feed of the past day (spec FR-1, EC-1; docs/API.md GET /feed).

The feed is read through the outbound gateway (`src.sources.http_get`) with max_age_s = 60, and at
most once a minute here as well. Each earthquake is classified against the current settings, so a
change of the trigger magnitude shows on the next check. What the agent did with each earthquake
is remembered in var/feed_state.json.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from pathlib import Path
from typing import Callable

from .store import iso, read_json, write_json

log = logging.getLogger("quakenet.agent")

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
USGS_ID = re.compile(r"[a-z0-9]{4,20}")
MAX_QUAKES = 100
REFRESH_S = 60.0
HOUR = 3600.0


class FeedUnavailable(Exception):
    """The feed could not be read and there is no earlier copy."""


def parse_feed(body: bytes) -> list[dict]:
    """Earthquakes of a USGS GeoJSON summary feed, newest first. Malformed entries are skipped."""
    doc = json.loads(body.decode("utf-8"))
    out = []
    for f in doc.get("features", []) if isinstance(doc, dict) else []:
        try:
            uid = str(f["id"])
            props, coords = f["properties"], f["geometry"]["coordinates"]
            mag, t = props.get("mag"), props.get("time")
            lon, lat, depth = (float(c) for c in coords[:3])
            if (not USGS_ID.fullmatch(uid) or isinstance(mag, bool) or not isinstance(mag, (int, float))
                    or not isinstance(t, (int, float)) or not all(map(math.isfinite, (mag, lat, lon, depth)))):
                continue
            place = props.get("place")
            out.append(dict(usgs_id=uid, place=str(place)[:200] if place else "", magnitude=float(mag),
                            time_utc=iso(t / 1000.0), time_s=t / 1000.0, lat=lat, lon=lon, depth_km=depth))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    out.sort(key=lambda q: q["time_s"], reverse=True)
    return out[:MAX_QUAKES]


def classify(quake: dict, settings: dict, state: dict) -> dict:
    """The public row of GET /feed for one earthquake."""
    threshold = float(settings["trigger_magnitude"])
    would = quake["magnitude"] >= threshold
    entry = state.get(quake["usgs_id"]) or {}
    status, reason, event_id = ("pending" if would else "below_threshold"), None, None
    if entry.get("status") == "planned" and entry.get("event_id"):
        status, event_id = "planned", entry["event_id"]
    elif would and entry.get("status") == "skipped":
        status, reason = "skipped", entry.get("reason") or "unusable"
    elif would and entry.get("status") == "waiting":
        reason = entry.get("reason")
    return dict(usgs_id=quake["usgs_id"], place=quake["place"], magnitude=quake["magnitude"],
                time_utc=quake["time_utc"], lat=quake["lat"], lon=quake["lon"], depth_km=quake["depth_km"],
                would_trigger=would, status=status, reason=reason, event_id=event_id)


class Feed:
    """The feed, its classification and the per-earthquake state. Thread-safe."""

    def __init__(self, state_path: Path, http_get: Callable | None = None, clock: Callable[[], float] = time.time):
        self._state_path = Path(state_path)
        self._get = http_get
        self._clock = clock
        self._lock = threading.Lock()
        self._quakes: list[dict] | None = None
        self._retrieved: float | None = None
        self._attempted: float | None = None
        self._fetch_lock = threading.Lock()
        state = read_json(self._state_path, {})
        self._state: dict = state if isinstance(state, dict) else {}

    # ------------------------------------------------------------------ reading the feed
    def _fetch(self) -> None:
        get = self._get
        if get is None:
            from src.sources import http_get as get
        body = get(FEED_URL, max_age_s=int(REFRESH_S))
        quakes = parse_feed(body)
        with self._lock:
            self._quakes, self._retrieved = quakes, self._clock()

    def quakes(self) -> tuple[list[dict], float]:
        """The latest feed, read again when the last attempt is more than a minute old. When a read
        fails, the last good copy is served; with no copy at all, FeedUnavailable is raised."""
        with self._fetch_lock:                       # one reader at a time; the others wait for its answer
            with self._lock:
                due = self._attempted is None or self._clock() - self._attempted >= REFRESH_S
                if due:
                    self._attempted = self._clock()
            if due:
                try:
                    self._fetch()
                except Exception:
                    log.warning("USGS feed could not be read", exc_info=True)
        with self._lock:
            if self._quakes is None:
                raise FeedUnavailable("The USGS feed could not be read.")
            return list(self._quakes), float(self._retrieved)

    def find(self, usgs_id: str) -> dict | None:
        quakes, _ = self.quakes()
        return next((q for q in quakes if q["usgs_id"] == usgs_id), None)

    def snapshot(self, settings: dict) -> dict:
        quakes, retrieved = self.quakes()
        state = self.state()
        return dict(retrieved_utc=iso(retrieved), source_url=FEED_URL,
                    threshold=float(settings["trigger_magnitude"]), live_enabled=bool(settings["live_enabled"]),
                    quakes=[classify(q, settings, state) for q in quakes])

    # ------------------------------------------------------------------ what was done with each earthquake
    def state(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self._state.items() if isinstance(v, dict)}

    def mark(self, usgs_id: str, status: str, *, reason: str | None = None, event_id: str | None = None,
             job_id: str | None = None) -> None:
        if not USGS_ID.fullmatch(usgs_id):
            raise ValueError("bad usgs id")
        with self._lock:
            self._state[usgs_id] = dict(status=status, reason=reason, event_id=event_id, job_id=job_id,
                                        at=self._clock())
            if len(self._state) > 2000:                 # forget the oldest
                for key in sorted(self._state, key=lambda k: self._state[k].get("at", 0))[:500]:
                    del self._state[key]
            try:
                write_json(self._state_path, self._state)
            except OSError:
                log.exception("could not save the feed state")

    def started_last_hour(self) -> int:
        now = self._clock()
        with self._lock:
            return sum(1 for v in self._state.values()
                       if v.get("status") in ("starting", "planned") and now - float(v.get("at", 0)) < HOUR)

    def reason_not_to_start(self, quake: dict, settings: dict) -> str | None:
        """Why the agent must not start on this earthquake now, or None. Cheap checks only."""
        if quake["magnitude"] < float(settings["trigger_magnitude"]):
            return (f"magnitude {quake['magnitude']:g} is below the trigger magnitude "
                    f"{float(settings['trigger_magnitude']):g}")
        entry = self.state().get(quake["usgs_id"]) or {}
        if entry.get("status") in ("starting", "planned"):
            return "the agent has already started on this earthquake"
        if entry.get("status") == "skipped":
            return entry.get("reason") or "skipped earlier"
        age_h = (self._clock() - quake["time_s"]) / HOUR
        if age_h > float(settings["monitor_hours"]):
            return "the earthquake is older than the monitoring window"
        return None
