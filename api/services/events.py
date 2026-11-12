"""Event registry: the allowlist of earthquakes the API can serve.

To add an event, register another `EventSpec` with its own loader. Nothing here fetches data;
the source URLs are read from the cached files and only reported back, never requested.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.geometry import DATA_DIR, DECISION_HOURS, Instance, load_instance

from ..errors import NotFound

log = logging.getLogger("quakenet.api")


@dataclass(frozen=True)
class SourceSpec:
    name: str
    file: Path           # cached file on disk
    url_key: str         # key of the source URL inside the file's "meta" block


@dataclass(frozen=True)
class EventSpec:
    id: str
    name: str
    magnitude: float
    time_utc: str
    region: str
    available: bool
    load: Callable[[], Instance]
    decision_hours: int = DECISION_HOURS
    sources: tuple[SourceSpec, ...] = ()

    def public(self) -> dict:
        return dict(id=self.id, name=self.name, magnitude=self.magnitude, time_utc=self.time_utc,
                    region=self.region, available=self.available)


class EventRegistry:
    def __init__(self) -> None:
        self._events: dict[str, EventSpec] = {}

    def register(self, spec: EventSpec) -> None:
        self._events[spec.id] = spec

    def get(self, event_id: str) -> EventSpec:
        spec = self._events.get(event_id)
        if spec is None or not spec.available:
            raise NotFound("Unknown event.")
        return spec

    def list(self) -> list[dict]:
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


def default_registry(region: str = "local") -> EventRegistry:
    registry = EventRegistry()
    registry.register(EventSpec(
        id="ridgecrest2019", name="Ridgecrest, California", magnitude=7.1, time_utc="2019-07-06T03:19:53Z",
        region=region, available=True, load=load_instance,
        sources=(SourceSpec("USGS ComCat", DATA_DIR / "events.json", "event_url"),
                 SourceSpec("IRIS/EarthScope FDSN stations", DATA_DIR / "stations.json", "station_url"))))
    return registry
