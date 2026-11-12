"""Event registry: the allowlist of earthquakes the API can serve.

Ridgecrest 2019 is built in and keeps the v1 instance (src/geometry.load_instance), so the numbers
of the v1 endpoints do not change. Every other event comes from the science layer's registry
(`src.instances.list_events`), which includes benchmark earthquakes and live ones started from the
feed. Nothing here fetches data; the source URLs are read from cached files and only reported back.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from src import geometry
from src.geometry import DATA_DIR, DECISION_HOURS, Instance, load_instance

from ..errors import NotFound

log = logging.getLogger("quakenet.api")

EVENT_ID = re.compile(r"[a-z0-9_-]{1,40}")
BUILTIN = "ridgecrest2019"


@dataclass(frozen=True)
class SourceSpec:
    name: str
    file: Path           # cached file on disk
    url_key: str         # key of the source URL inside the file's "meta" block


@dataclass(frozen=True)
class Loaded:
    """An event's v1 instance plus the map metadata v2 adds to it."""
    inst: Instance
    lat0: float
    lon0: float
    feasibility_checked: bool
    to_latlon: Callable[[float, float], tuple[float, float]]


@dataclass(frozen=True)
class EventSpec:
    id: str
    name: str
    magnitude: float
    time_utc: str
    region: str
    available: bool
    load: Callable[[], Loaded]
    kind: str = "benchmark"
    usgs_id: str = ""
    lat: float = 0.0
    lon: float = 0.0
    decision_hours: int = DECISION_HOURS
    sources: tuple[SourceSpec, ...] = field(default=())

    def public(self) -> dict:
        return dict(id=self.id, name=self.name, magnitude=self.magnitude, time_utc=self.time_utc,
                    region=self.region, available=self.available, kind=self.kind, usgs_id=self.usgs_id,
                    lat=self.lat, lon=self.lon)


def _time_text(value) -> str:
    if isinstance(value, datetime):
        t = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = str(value)
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
        t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return text


def _offline() -> bool:
    import os
    return os.environ.get("QUAKENET_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


class EventRegistry:
    def __init__(self, region: str = "local", discover: Callable[[], list[dict]] | None = None,
                 loader: Callable[[str], Loaded] | None = None) -> None:
        self._region = region
        self._events: dict[str, EventSpec] = {}
        self._discover, self._loader = discover, loader

    def register(self, spec: EventSpec) -> None:
        self._events[spec.id] = spec

    def refresh(self) -> None:
        """Add the events the science layer knows. A failure there leaves the built-in events."""
        if self._discover is None:
            return
        try:
            rows = self._discover()
        except Exception:
            log.warning("could not list the science layer's events", exc_info=True)
            return
        for row in rows or []:
            try:
                eid = str(row["id"])
                if not EVENT_ID.fullmatch(eid) or eid == BUILTIN:
                    continue
                mag, lat, lon = float(row["magnitude"]), float(row["lat"]), float(row["lon"])
                if not all(map(math.isfinite, (mag, lat, lon))):
                    continue
                kind = row.get("kind") if row.get("kind") in ("benchmark", "live") else "benchmark"
                loader = self._loader
                self._events[eid] = EventSpec(
                    id=eid, name=str(row.get("name") or eid)[:120], magnitude=mag, time_utc=_time_text(row["time_utc"]),
                    region=self._region, available=bool(row.get("cached")) or not _offline(),
                    load=(lambda e=eid: loader(e)) if loader else _not_loadable, kind=kind,
                    usgs_id=str(row.get("usgs_id") or ""), lat=lat, lon=lon)
            except (KeyError, TypeError, ValueError):
                log.warning("skipping a malformed event row from the science layer")

    def get(self, event_id: str) -> EventSpec:
        if not EVENT_ID.fullmatch(event_id or ""):
            raise NotFound("Unknown event.")
        if event_id not in self._events:
            self.refresh()
        spec = self._events.get(event_id)
        if spec is None or not spec.available:
            raise NotFound("Unknown event.")
        return spec

    def list(self) -> list[dict]:
        self.refresh()
        return [spec.public() for spec in self._events.values()]

    def sources(self) -> list[dict]:
        """Status of every cached data file. `retrieved_utc` is the cache file's modification time:
        the cached files do not record when they were downloaded."""
        out, seen = [], set()
        for spec in self._events.values():
            for src in spec.sources:
                if (src.name, src.file) in seen:
                    continue
                seen.add((src.name, src.file))
                url, retrieved, cached = "", None, src.file.is_file()
                if cached:
                    try:
                        url = str(json.loads(src.file.read_text(encoding="utf-8"))["meta"][src.url_key])
                        retrieved = datetime.fromtimestamp(src.file.stat().st_mtime, timezone.utc) \
                            .strftime("%Y-%m-%dT%H:%M:%SZ")
                    except (OSError, ValueError, KeyError, TypeError):
                        log.exception("could not read source metadata from %s", src.file)
                        cached = False
                out.append(dict(name=src.name, cached=cached, retrieved_utc=retrieved, url=url))
        return out


def _not_loadable() -> Loaded:
    raise RuntimeError("no loader for this event")


def ridgecrest_latlon(x: float, y: float) -> tuple[float, float]:
    """Inverse of src.geometry.to_km (the v1 grid centred on LAT0, LON0)."""
    lat = geometry.LAT0 + y / geometry.KM_PER_DEG
    lon = geometry.LON0 + x / (geometry.KM_PER_DEG * math.cos(math.radians(geometry.LAT0)))
    return float(lat), float(lon)


def load_ridgecrest() -> Loaded:
    # The v1 candidates are a regular grid with no road or slope check, so feasibility is not checked.
    return Loaded(load_instance(), geometry.LAT0, geometry.LON0, False, ridgecrest_latlon)


def load_from_science(event_id: str, toolkit_factory: Callable) -> Loaded:
    """The v1-style instance of any other event: plan on the aftershocks of the first
    DECISION_HOURS hours (topped up with synthetic ones when too few), test on the later ones."""
    tk = toolkit_factory()
    data = tk.load_event_data(event_id)
    events, _ = tk.planning_events(data, float(DECISION_HOURS), min_real=30, seed=0)
    candidates, _ = tk.select_sites(data, events, n=10)
    a = np.asarray(data.aftershocks, float).reshape(-1, 5)
    valid = a[a[:, 4] > DECISION_HOURS][:, :3]
    inst = tk.make_instance(data, np.asarray(candidates, float), np.asarray(events, float), k=4, valid=valid)
    return Loaded(inst, float(data.lat0), float(data.lon0), bool(data.feasibility_checked), data.to_latlon)


def default_registry(region: str = "local", toolkit_factory: Callable | None = None) -> EventRegistry:
    discover = loader = None
    if toolkit_factory is not None:
        def discover():
            return toolkit_factory().list_events()

        def loader(event_id: str) -> Loaded:
            return load_from_science(event_id, toolkit_factory)
    registry = EventRegistry(region, discover, loader)
    main = max(json.loads((DATA_DIR / "events.json").read_text())["events"], key=lambda e: e["mag"])
    registry.register(EventSpec(
        id=BUILTIN, name="Ridgecrest, California", magnitude=7.1, time_utc="2019-07-06T03:19:53Z",
        region=region, available=True, load=load_ridgecrest, kind="benchmark", usgs_id=str(main["id"]),
        lat=float(main["lat"]), lon=float(main["lon"]),
        sources=(SourceSpec("USGS ComCat", DATA_DIR / "events.json", "event_url"),
                 SourceSpec("IRIS/EarthScope FDSN stations", DATA_DIR / "stations.json", "station_url"))))
    return registry
