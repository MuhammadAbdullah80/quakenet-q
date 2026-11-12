"""The agent's run on one earthquake (docs/API.md, "Sequences"; spec FR-23 to FR-27).

A first plan at hour 0, then a check every `step_hours`. A check uses only the aftershocks
recorded up to the simulated (replay) or real (live) time of that step. Drift is declared when
  * the centroid of the aftershocks of the last 6 hours has moved more than `drift_centroid_km`
    from the centroid the current plan was made for, or
  * the realised score of the current plan, on the aftershocks recorded since it was made, is
    more than `drift_score_drop` (a fraction) below its predicted score;
and drift triggers a re-plan with a move cost. The sequence is saved after every step, so it can
be read while it runs. Predicted and realised scores go into memory's track record.
"""
from __future__ import annotations

import logging
import math
import re
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .memory import Memory
from .planner import Budget, Plan, information_scale, make_plan, model_errors, realised_score
from .store import read_json, utc_now, write_json
from .toolkit import Toolkit

log = logging.getLogger("quakenet.agent")

EVENT_ID = re.compile(r"[a-z0-9_-]{1,40}")
RECENT_HOURS = 6.0           # window of the drift centroid (FR-24)
MIN_CENTROID_EVENTS = 3      # fewer recent aftershocks than this: no centroid test
MIN_REALISED_EVENTS = 5      # fewer new aftershocks than this: no realised score yet
MIN_SITES = 6                # EC-4: below this, there are not enough reachable sites
KM_PER_DEG = 111.19
PUBLIC_SETTINGS = ("sensors", "candidates", "risk_weight", "move_cost", "drift_centroid_km", "drift_score_drop")


class AgentSkip(Exception):
    """The agent declines to run, for a reason that is safe to show to the user."""


def to_km(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Equirectangular projection, the same formula as src/geometry.py and src/sources.Projection."""
    return ((lon - lon0) * math.cos(math.radians(lat0)) * KM_PER_DEG, (lat - lat0) * KM_PER_DEG)


def step_hours_list(hours: int, step: int) -> list[int]:
    out = list(range(0, int(hours) + 1, int(step)))
    if out[-1] != hours:
        out.append(int(hours))
    return out


class SequenceStore:
    """var/sequences/{event_id}.json (the GET /sequence body) and {event_id}.plan.json (GET /plan)."""

    def __init__(self, directory: Path):
        self._dir = Path(directory)

    def _path(self, event_id: str, suffix: str) -> Path:
        if not EVENT_ID.fullmatch(event_id or ""):
            raise ValueError("bad event id")
        return self._dir / f"{event_id}{suffix}"

    def save(self, seq: dict) -> None:
        write_json(self._path(seq["event_id"], ".json"), seq)

    def load(self, event_id: str) -> dict | None:
        value = read_json(self._path(event_id, ".json"))
        return value if isinstance(value, dict) else None

    def save_plan(self, event_id: str, plan: dict) -> None:
        write_json(self._path(event_id, ".plan.json"), plan)

    def clear_plan(self, event_id: str) -> None:
        try:
            self._path(event_id, ".plan.json").unlink(missing_ok=True)
        except OSError:
            log.exception("could not remove the previous plan of %s", event_id)

    def load_plan(self, event_id: str) -> dict | None:
        value = read_json(self._path(event_id, ".plan.json"))
        return value if isinstance(value, dict) else None

    def mark_interrupted(self) -> None:
        """At start-up: a sequence that was running when the server stopped cannot resume."""
        if not self._dir.is_dir():
            return
        for path in self._dir.glob("*.json"):
            if path.name.endswith(".plan.json"):
                continue
            seq = read_json(path)
            if isinstance(seq, dict) and seq.get("status") == "running":
                seq.update(status="failed", finished_utc=utc_now())
                try:
                    write_json(path, seq)
                except OSError:
                    log.exception("could not mark sequence %s as interrupted", path.name)


class SequenceRun:
    """State of one sequence. Call `step(hour)` for each hour of `hours()` in order, then `finish()`."""

    def __init__(self, data, *, mode: str, hours: int, step_hours: int, settings: dict, toolkit: Toolkit,
                 memory: Memory, store: SequenceStore, budget: Budget = Budget(),
                 refresh: Callable[[], object] | None = None):
        if mode not in ("replay", "live"):
            raise ValueError("mode must be replay or live")
        self.data, self.mode, self.hours_total, self.step_hours = data, mode, int(hours), int(step_hours)
        self.settings = dict(settings)            # frozen for the whole sequence
        self.toolkit, self.memory, self.store, self.budget = toolkit, memory, store, budget
        self.refresh = refresh                    # live: fetch newer data before each check
        self.event_id = data.event_id
        self.plan: Plan | None = None
        self.plan_hour = 0.0
        self.plan_stage = "first_plan"
        self.plan_events = 0
        self.ref_centroid: tuple[float, float] | None = None
        self.last_realised: float | None = None
        self.last_since: np.ndarray | None = None
        self.errors_by_model: dict[str, list[float]] = {}
        self.candidates = None
        self.plans_made = self.moves_total = 0
        self.doc = self._header()
        self.store.clear_plan(self.event_id)       # a new sequence replaces the event's previous one
        self._save()                               # visible (with no steps yet) as soon as it starts

    def hours(self) -> list[int]:
        return step_hours_list(self.hours_total, self.step_hours)

    # ------------------------------------------------------------------ the saved document
    def _header(self) -> dict:
        d = self.data
        mx, my = to_km(d.lat, d.lon, d.lat0, d.lon0)
        return dict(event_id=self.event_id, mode=self.mode, status="running", hours_done=0,
                    hours_total=self.hours_total, started_utc=utc_now(), finished_utc=None,
                    settings={k: self.settings[k] for k in PUBLIC_SETTINGS},
                    grid=dict(lat0=float(d.lat0), lon0=float(d.lon0)),
                    feasibility_checked=bool(d.feasibility_checked),
                    mainshock=dict(x=round(mx, 3), y=round(my, 3), depth=float(d.depth_km)),
                    stations=[dict(name=str(name), x=round(float(x), 3), y=round(float(y), 3))
                              for name, (x, y) in zip(d.station_names, np.asarray(d.stations, float))],
                    candidates=[], aftershocks=self._aftershock_list(self.hours_total if self.mode == "replay" else 0),
                    steps=[], current_sites=[], plans_made=0, moves_total=0)

    def _aftershock_list(self, up_to_hours: float) -> list[list[float]]:
        a = self._visible(up_to_hours)
        return [[round(float(v), 3) for v in row[:4]] + [round(float(row[4]), 4)] for row in a]

    def _save(self) -> None:
        try:
            self.store.save(self.doc)
        except OSError:
            log.exception("could not save sequence %s", self.event_id)

    # ------------------------------------------------------------------ data visibility
    def _visible(self, hour: float) -> np.ndarray:
        """Real aftershocks recorded up to `hour` after the mainshock. Nothing later is ever used."""
        a = np.asarray(self.data.aftershocks, float).reshape(-1, 5)
        return a[a[:, 4] <= hour + 1e-9]

    def _planning_events(self, hour: float) -> tuple[np.ndarray, bool]:
        events, synthetic = self.toolkit.planning_events(self.data, hour, min_real=int(self.settings["min_real_aftershocks"]),
                                                         seed=self.plans_made)
        events = np.asarray(events, float)
        real = events[events[:, 4] > 0] if len(events) else events
        if len(real) and real[:, 4].max() > hour + 1e-9:       # a guard: the science layer must not leak
            raise RuntimeError("planning_events returned an aftershock from after the planning time")
        return events, bool(synthetic)

    # ------------------------------------------------------------------ steps
    def step(self, hour: int) -> dict:
        if self.refresh is not None and self.plan is not None:
            try:
                self.data = self.refresh()
            except Exception:                    # keep the data we have; the next check tries again
                log.warning("live data refresh failed for %s; using the previous data", self.event_id)
        step = self._first_plan(float(hour)) if self.plan is None else self._check(float(hour))
        step["hour"] = hour
        self.doc["steps"].append(step)
        self.doc.update(hours_done=hour, current_sites=list(self.plan.sites), plans_made=self.plans_made,
                        moves_total=self.moves_total)
        if self.mode == "live":
            self.doc["aftershocks"] = self._aftershock_list(hour)
        self._save()
        return step

    def _publish(self, plan: Plan, hour: float, stage: str) -> None:
        d, details = self.data, plan.details
        by_id = {s["id"]: s for s in details["sites"]}
        sites = []
        for i in plan.sites:
            c = self.doc["candidates"][i]
            sites.append(dict(id=i, x=c["x"], y=c["y"], lat=c["lat"], lon=c["lon"], risk=by_id[i]["risk"],
                              single_gain=by_id[i]["single_gain"], reason=by_id[i]["reason"], backups=c["backups"]))
        p = plan.public
        self.store.save_plan(self.event_id, dict(
            event_id=self.event_id, stage=stage, hour=int(hour), created_utc=utc_now(), sites=sites, moves=p["moves"],
            objective=p["objective"], exact_rank=p["exact_rank"], quantum_agreed=p["quantum_agreed"],
            p_opt_per_shot=p["p_opt_per_shot"], expected_error_km=p["expected_error_km"],
            expert_rule_error_km=p["expert_rule_error_km"], confidence=self.memory.confidence(),
            feasibility_checked=bool(d.feasibility_checked), warm_start=details["warm_start"],
            objective_kind=details["objective_kind"], layers=details["layers"]))

    def _first_plan(self, hour: float) -> dict:
        events, synthetic = self._planning_events(hour)
        candidates, backups = self.toolkit.select_sites(self.data, events, n=int(self.settings["candidates"]))
        candidates = np.asarray(candidates, float)
        if len(candidates) < max(MIN_SITES, int(self.settings["sensors"]) + 1):
            raise AgentSkip("insufficient reachable sites")
        self.candidates = candidates
        self.doc["candidates"] = []
        for i, (x, y) in enumerate(candidates):
            lat, lon = self.data.to_latlon(float(x), float(y))
            ups = backups[i] if i < len(backups) else []
            self.doc["candidates"].append(dict(id=i, x=round(float(x), 3), y=round(float(y), 3),
                                               lat=round(float(lat), 5), lon=round(float(lon), 5),
                                               backups=[dict(lat=round(float(a), 5), lon=round(float(b), 5))
                                                        for a, b in ups]))
        plan = self._plan(events, current=None)
        self._adopt(plan, hour, "first_plan", events, recent=None)
        return dict(hour=0, stage="first_plan", aftershocks_real=int(len(self._visible(hour))),
                    aftershocks_used=int(len(events)), synthetic=synthetic,
                    centroid=dict(x=round(plan.centroid[0], 3), y=round(plan.centroid[1], 3)), centroid_shift_km=0.0,
                    predicted_score=round(plan.predicted_score, 3), realised_score=None, score_drop=None,
                    drift=False, drift_reason=None, sites=list(plan.sites), plan=plan.public)

    def _plan(self, events: np.ndarray, current) -> Plan:
        plan = make_plan(self.data, events, self.candidates, current=current, settings=self.settings,
                         memory=self.memory, toolkit=self.toolkit, budget=self.budget, seed=self.plans_made)
        self.plans_made += 1
        return plan

    def _adopt(self, plan: Plan, hour: float, stage: str, events: np.ndarray, recent) -> None:
        self.moves_total += len(plan.public["moves"])
        self.plan, self.plan_hour, self.plan_stage, self.plan_events = plan, hour, stage, len(events)
        self.ref_centroid = tuple(recent[:, :2].mean(axis=0)) if recent is not None and len(recent) >= MIN_CENTROID_EVENTS \
            else plan.centroid
        self.last_realised = self.last_since = None
        self._publish(plan, hour, stage)

    def _check(self, hour: float) -> dict:
        s = self.settings
        visible = self._visible(hour)
        recent = visible[visible[:, 4] > hour - RECENT_HOURS]
        if len(recent) >= MIN_CENTROID_EVENTS:
            centroid = tuple(float(v) for v in recent[:, :2].mean(axis=0))
            shift = float(np.hypot(centroid[0] - self.ref_centroid[0], centroid[1] - self.ref_centroid[1]))
        else:
            centroid, shift = tuple(self.ref_centroid), 0.0
        since = visible[visible[:, 4] > self.plan_hour + 1e-9]
        predicted = self.plan.predicted_score
        realised = drop = None
        if len(since) >= MIN_REALISED_EVENTS:
            realised = realised_score(self.plan, since, settings=s, toolkit=self.toolkit,
                                      reference_count=self.plan_events)
            self.last_realised, self.last_since = realised, since
            scale = information_scale(self.plan, s)
            drop = (predicted - realised) / scale if scale else 0.0
        reasons = []
        if shift > float(s["drift_centroid_km"]):
            reasons.append(f"centroid moved {shift:.1f} km")
        if drop is not None and drop > float(s["drift_score_drop"]):
            reasons.append(f"score fell {round(100 * drop)}%")
        step = dict(stage="check", aftershocks_real=int(len(visible)), aftershocks_used=int(len(since)) if realised is not None else 0,
                    synthetic=False, centroid=dict(x=round(centroid[0], 3), y=round(centroid[1], 3)),
                    centroid_shift_km=round(shift, 3), predicted_score=round(predicted, 3),
                    realised_score=None if realised is None else round(realised, 3),
                    score_drop=None if drop is None else round(drop, 4), drift=bool(reasons),
                    drift_reason="; ".join(reasons) or None, sites=list(self.plan.sites), plan=None)
        if reasons:
            self._record_current()
            events, synthetic = self._planning_events(hour)
            plan = self._plan(events, current=self.plan.sites)
            self._adopt(plan, hour, "replan", events, recent)
            step.update(stage="replan", plan=plan.public, sites=list(plan.sites), synthetic=synthetic,
                        aftershocks_used=int(len(events)))
        return step

    def _record_current(self) -> None:
        """Store the current plan's predicted and latest realised score (FR-27), and how well each
        velocity model's score carried over (used for the model weights, FR-28)."""
        if self.plan is None or self.last_realised is None:
            return
        self.memory.record(self.event_id, int(self.plan_hour), self.plan_stage, self.plan.predicted_score,
                           self.last_realised, scale=information_scale(self.plan, self.settings))
        try:
            for name, err in model_errors(self.plan, self.last_since, settings=self.settings,
                                          toolkit=self.toolkit).items():
                self.errors_by_model.setdefault(name, []).append(err)
        except Exception:
            log.warning("could not rate the velocity models for %s", self.event_id, exc_info=True)
        self.last_realised = self.last_since = None

    def finish(self) -> None:
        self._record_current()
        if self.errors_by_model:
            self.memory.update_model_weights({name: max(0.0, 1.0 - float(np.median(errs)))
                                              for name, errs in self.errors_by_model.items()})
        self.memory.finish_sequence()
        self.doc.update(status="done", finished_utc=utc_now())
        self._save()

    def fail(self) -> None:
        self.doc.update(status="failed", finished_utc=utc_now())
        self._save()


def run_replay(data, *, hours: int, step_hours: int, settings: dict, toolkit: Toolkit, memory: Memory,
               store: SequenceStore, budget: Budget = Budget()) -> dict:
    """Play a past earthquake forward on a simulated clock. Returns the job result."""
    run = SequenceRun(data, mode="replay", hours=hours, step_hours=step_hours, settings=settings, toolkit=toolkit,
                      memory=memory, store=store, budget=budget)
    t0 = time.time()
    try:
        for hour in run.hours():
            run.step(hour)
    except BaseException:
        run.fail()
        raise
    run.finish()
    log.info("replay of %s: %d steps, %d plans, %.1f s", data.event_id, len(run.doc["steps"]), run.plans_made,
             time.time() - t0)
    return dict(event_id=data.event_id, steps=len(run.doc["steps"]))
