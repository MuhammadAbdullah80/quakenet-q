"""Settings a scientist can edit (GET/PUT /settings in docs/API.md).

Saved as JSON in var/settings.json with an atomic write. Every change is validated in full
before anything is applied: unknown keys, wrong types and out-of-range values are rejected and
change nothing. The agent reads the settings afresh at every step, so a change (for example the
trigger magnitude) takes effect on the next feed check without a restart.
"""
from __future__ import annotations

import copy
import math
import threading
from pathlib import Path

from .store import read_json, utc_now, write_json

DEFAULTS: dict = {
    "trigger_magnitude": 6.5, "station_radius_km": 100, "sensors": 4, "candidates": 10,
    "risk_weight": 150, "move_cost": 40, "monitor_interval_hours": 1, "monitor_hours": 72,
    "drift_centroid_km": 5, "drift_score_drop": 0.2, "min_real_aftershocks": 30,
    "qaoa_layers": 3, "shots": 1024, "hearing_range": True, "live_enabled": False,
    "max_plans_per_hour": 4,
}
LIMITS: dict[str, tuple[float, float]] = {
    "trigger_magnitude": (3.0, 9.0), "station_radius_km": (20, 300), "sensors": (2, 4),
    "candidates": (8, 10), "risk_weight": (0, 1000), "move_cost": (0, 500),
    "monitor_interval_hours": (1, 12), "monitor_hours": (6, 168),
    "drift_centroid_km": (1, 50), "drift_score_drop": (0.05, 0.9),
    "min_real_aftershocks": (5, 200), "qaoa_layers": (1, 5), "shots": (128, 4096),
    "max_plans_per_hour": (1, 20),
}
INTEGER_KEYS = frozenset({"sensors", "candidates", "monitor_interval_hours", "monitor_hours",
                          "min_real_aftershocks", "qaoa_layers", "shots", "max_plans_per_hour"})
BOOL_KEYS = frozenset({"hearing_range", "live_enabled"})
EDITABLE = tuple(DEFAULTS)


class SettingsError(ValueError):
    """A rejected change. The message names the key and the rule, never the rejected value."""


def check(changes) -> dict:
    """Validated copy of a change set. Raises SettingsError on the first problem."""
    if not isinstance(changes, dict):
        raise SettingsError("The settings must be a JSON object.")
    out = {}
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise SettingsError("Unknown setting." if not isinstance(key, str) or not key.isidentifier()
                                or len(key) > 40 else f"Unknown setting: {key}.")
        if key in BOOL_KEYS:
            if not isinstance(value, bool):
                raise SettingsError(f"{key} must be true or false.")
            out[key] = value
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsError(f"{key} must be a number.")
        if key in INTEGER_KEYS and not isinstance(value, int):
            raise SettingsError(f"{key} must be a whole number.")
        if not math.isfinite(value):
            raise SettingsError(f"{key} must be a finite number.")
        lo, hi = LIMITS[key]
        if not lo <= value <= hi:
            raise SettingsError(f"{key} must be between {lo} and {hi}.")
        out[key] = value
    return out


class AgentSettings:
    """Thread-safe settings with persistence. `get()` returns a fresh copy every time."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._values = dict(DEFAULTS)
        self._updated = utc_now()
        saved = read_json(self._path)
        if isinstance(saved, dict):
            try:
                values = saved.get("values", {})
                self._values.update(check({k: v for k, v in values.items() if k in DEFAULTS}))
                if isinstance(saved.get("updated_utc"), str):
                    self._updated = saved["updated_utc"]
            except (SettingsError, AttributeError):
                pass                      # a damaged file falls back to the defaults

    def values(self) -> dict:
        """The editable values only (what the agent uses)."""
        with self._lock:
            return dict(self._values)

    def get(self) -> dict:
        """The full object of GET /settings."""
        with self._lock:
            return dict(self._values, limits={k: list(v) for k, v in copy.deepcopy(LIMITS).items()},
                        updated_utc=self._updated)

    def update(self, changes) -> dict:
        """Apply a validated change set atomically and save it. Returns the full object."""
        clean = check(changes)
        with self._lock:
            if clean:
                values = dict(self._values, **clean)
                updated = utc_now()
                write_json(self._path, {"values": values, "updated_utc": updated})   # disk first
                self._values, self._updated = values, updated
        return self.get()
