"""What the agent remembers across earthquakes (GET /memory in docs/API.md).

Files under var/memory/:
  angles.json        optimised QAOA angles per (candidates, sensors, layers); the median is the
                     warm start of the next plan of the same size (spec FR-16)
  weights.json       velocity-model weights (FR-28): each model's realised accuracy summed over
                     sequences, Laplace-smoothed with equal priors, normalised to sum to 1
  track_record.json  predicted against realised plan scores (FR-27); their median relative error
                     gives the confidence level of new plans (FR-22)
  meta.json          number of finished sequences
"""
from __future__ import annotations

import math
import threading
from pathlib import Path

import numpy as np

from .store import read_json, write_json

MAX_ANGLE_SETS = 50          # per key; the oldest are dropped
MAX_TRACK_RECORD = 500
HIGH, MEDIUM = 0.25, 0.50    # median relative error thresholds of the confidence levels
DEFAULT_MODELS = ("uniform 5.5 km/s", "uniform 6.0 km/s", "uniform 6.5 km/s")


def angle_key(candidates: int, sensors: int, layers: int) -> str:
    return f"{int(candidates)}-{int(sensors)}-{int(layers)}"


def confidence_from_errors(errors) -> str:
    errors = [float(e) for e in errors if e is not None and math.isfinite(float(e))]
    if not errors:
        return "unrated"
    median = float(np.median(errors))
    return "high" if median <= HIGH else "medium" if median <= MEDIUM else "low"


class Memory:
    def __init__(self, directory: Path, models: tuple[str, ...] = DEFAULT_MODELS):
        self._dir = Path(directory)
        self._lock = threading.Lock()
        self._models = tuple(models)
        self._angles = self._load("angles.json", dict)
        self._weights = self._load("weights.json", dict)
        self._record = self._load("track_record.json", list)
        meta = self._load("meta.json", dict)
        self._sequences = int(meta.get("sequences", 0)) if isinstance(meta.get("sequences", 0), int) else 0

    def _load(self, name: str, kind):
        value = read_json(self._dir / name)
        return value if isinstance(value, kind) else kind()

    def _save(self, name: str, value) -> None:
        write_json(self._dir / name, value)

    # ------------------------------------------------------------------ angles
    def add_angles(self, candidates: int, sensors: int, layers: int, theta) -> None:
        theta = [float(t) for t in theta]
        if len(theta) != 2 * layers or not all(math.isfinite(t) for t in theta):
            raise ValueError("angles must be 2 * layers finite numbers")
        key = angle_key(candidates, sensors, layers)
        with self._lock:
            sets = [s for s in self._angles.get(key, []) if isinstance(s, list) and len(s) == 2 * layers]
            self._angles[key] = (sets + [theta])[-MAX_ANGLE_SETS:]
            self._save("angles.json", self._angles)

    def warm_start(self, candidates: int, sensors: int, layers: int) -> list[float] | None:
        """Element-wise median of the stored angles for this size, or None when there are none."""
        with self._lock:
            sets = [s for s in self._angles.get(angle_key(candidates, sensors, layers), [])
                    if isinstance(s, list) and len(s) == 2 * layers]
        return [float(v) for v in np.median(np.array(sets, float), axis=0)] if sets else None

    # ------------------------------------------------------------------ velocity models
    def model_weights(self) -> list[dict]:
        with self._lock:
            names = list(dict.fromkeys(list(self._models) + list(self._weights)))
            raw = {}
            for name in names:
                entry = self._weights.get(name, {})
                total, count = float(entry.get("accuracy_sum", 0.0)), int(entry.get("count", 0))
                raw[name] = (total + 1.0) / (count + 2.0)          # Laplace smoothing, equal priors
        norm = sum(raw.values()) or 1.0
        return [dict(name=name, weight=round(value / norm, 4)) for name, value in raw.items()]

    def update_model_weights(self, accuracy: dict[str, float]) -> None:
        """`accuracy` maps a model name to its realised accuracy in [0, 1] on one sequence."""
        with self._lock:
            for name, acc in accuracy.items():
                acc = min(1.0, max(0.0, float(acc)))
                entry = self._weights.setdefault(str(name), {"accuracy_sum": 0.0, "count": 0})
                entry["accuracy_sum"] = float(entry.get("accuracy_sum", 0.0)) + acc
                entry["count"] = int(entry.get("count", 0)) + 1
            self._save("weights.json", self._weights)

    # ------------------------------------------------------------------ track record
    def record(self, event_id: str, hour: float, stage: str, predicted: float, realised: float,
               scale: float | None = None) -> dict:
        """`scale` is what the error is relative to; default |predicted|."""
        denom = abs(scale) if scale else abs(predicted)
        error = abs(realised - predicted) / denom if denom else None
        entry = dict(event_id=event_id, hour=hour, stage=stage, predicted_score=round(float(predicted), 3),
                     realised_score=round(float(realised), 3),
                     error=None if error is None else round(float(error), 4))
        with self._lock:
            self._record = (self._record + [entry])[-MAX_TRACK_RECORD:]
            self._save("track_record.json", self._record)
        return entry

    def confidence(self) -> str:
        with self._lock:
            return confidence_from_errors([e.get("error") for e in self._record if isinstance(e, dict)])

    def finish_sequence(self) -> None:
        with self._lock:
            self._sequences += 1
            self._save("meta.json", {"sequences": self._sequences})

    # ------------------------------------------------------------------ the GET /memory body
    def snapshot(self) -> dict:
        with self._lock:
            angles = []
            for key, sets in sorted(self._angles.items()):
                try:
                    n, k, p = (int(v) for v in key.split("-"))
                except ValueError:
                    continue
                good = [s for s in sets if isinstance(s, list) and len(s) == 2 * p]
                if good:
                    angles.append(dict(key=key, sensors=k, candidates=n, layers=p, count=len(good),
                                       median=[round(float(v), 4) for v in np.median(np.array(good, float), axis=0)]))
            record = [dict(e) for e in self._record if isinstance(e, dict)]
            sequences = self._sequences
        return dict(angles=angles, model_weights=self.model_weights(), track_record=record,
                    confidence=self.confidence(), sequences=sequences)
