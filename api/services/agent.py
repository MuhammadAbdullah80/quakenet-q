"""The agent behind the v2 endpoints: settings, memory, sequences, the feed and the scheduler.

Logic lives in src/agent/; this service wires it to the job runner and maps its errors to the
API's domain errors. Nothing here knows about HTTP.

Threads: replays and the first plan of a live sequence run in the job runner's worker (one job at
a time). A scheduler thread wakes every `poll_s` seconds to advance live sequences whose next
check is due and, when live mode is on, to look at the feed. Heavy work in the two threads is
serialised by one compute lock. Any failure in the scheduler is logged and never reaches the API.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.agent.feed import USGS_ID, Feed
from src.agent.feed import FeedUnavailable as FeedDown
from src.agent.memory import Memory
from src.agent.planner import Budget
from src.agent.sequence import AgentSkip, SequenceRun, SequenceStore, run_replay, step_hours_list
from src.agent.settings import AgentSettings, SettingsError

from ..errors import FeedUnavailable, InvalidInput, JobRunning, NotBuilt, NotFound, RateLimited
from .events import EventRegistry
from .science import Cache

log = logging.getLogger("quakenet.api")
HOUR = 3600.0


class LiveSequence:
    def __init__(self, run: SequenceRun, hours: list[int], t0: float, usgs_id: str):
        self.run, self.hours, self.t0, self.usgs_id = run, hours, t0, usgs_id


class AgentService:
    def __init__(self, var_dir: Path, registry: EventRegistry, toolkit_factory: Callable, budget: Budget,
                 *, http_get: Callable | None = None, poll_s: float = 60.0, clock: Callable[[], float] = time.time,
                 noise: Callable | None = None):
        var_dir = Path(var_dir)
        self.settings = AgentSettings(var_dir / "settings.json")
        self.memory = Memory(var_dir / "memory")
        self.store = SequenceStore(var_dir / "sequences")
        self.store.mark_interrupted()
        self.feed = Feed(var_dir / "feed_state.json", http_get=http_get, clock=clock)
        self.registry, self.budget, self.poll_s, self.clock = registry, budget, poll_s, clock
        self._toolkit_factory = toolkit_factory
        self._noise = noise
        self._cache = Cache(4)
        self.compute = threading.Lock()
        self.jobs = None                                 # set by the app factory (the job runner needs us first)
        self._live: dict[str, LiveSequence] = {}
        self._live_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def toolkit(self):
        return self._toolkit_factory()

    # ------------------------------------------------------------------ settings and memory
    def get_settings(self) -> dict:
        return self.settings.get()

    def put_settings(self, changes: dict) -> dict:
        try:
            return self.settings.update(changes)
        except SettingsError as err:
            raise InvalidInput(str(err)) from None

    def get_memory(self) -> dict:
        return self.memory.snapshot()

    # ------------------------------------------------------------------ sequences and plans
    def sequence(self, event_id: str) -> dict:
        self.registry.get(event_id)
        seq = self.store.load(event_id)
        if seq is None:
            raise NotFound("No sequence has been run for this event.")
        return seq

    def plan(self, event_id: str) -> dict:
        self.registry.get(event_id)
        plan = self.store.load_plan(event_id)
        if plan is None:
            raise NotFound("No plan has been made for this event.")
        return plan

    def sequence_params(self, hours: int | None, step_hours: int | None) -> dict:
        s = self.settings.values()
        return dict(mode="replay", hours=int(hours if hours is not None else s["monitor_hours"]),
                    step_hours=int(step_hours if step_hours is not None else s["monitor_interval_hours"]))

    # ------------------------------------------------------------------ job execution (worker thread)
    def run_sequence_job(self, event_id: str, params: dict) -> dict:
        if params.get("mode") == "live":
            return self._start_live(str(params["usgs_id"]))
        tk = self.toolkit()
        with self.compute:
            data = tk.load_event_data(event_id)
            return run_replay(data, hours=int(params["hours"]), step_hours=int(params["step_hours"]),
                              settings=self.settings.values(), toolkit=tk, memory=self.memory, store=self.store,
                              budget=self.budget)

    def _start_live(self, usgs_id: str) -> dict:
        s = self.settings.values()
        radius = float(s["station_radius_km"])
        tk = self.toolkit()

        def fetch():
            return tk.event_from_usgs(usgs_id, station_radius_km=radius)
        try:
            data = fetch()
        except Exception as err:
            code = getattr(err, "code", "")
            reason = (f"no permanent station within {radius:g} km" if code == "NO_STATIONS"
                      else "the earthquake data could not be fetched")
            log.warning("live start on %s skipped (%s)", usgs_id, code or type(err).__name__, exc_info=True)
            self.feed.mark(usgs_id, "skipped", reason=reason)
            raise AgentSkip(reason) from None
        t0 = _timestamp(data.time_utc)
        elapsed_h = max(0.0, (self.clock() - t0) / HOUR)
        step, total = int(s["monitor_interval_hours"]), int(s["monitor_hours"])
        if elapsed_h > total:
            self.feed.mark(usgs_id, "skipped", reason="the earthquake is older than the monitoring window")
            raise AgentSkip("the earthquake is older than the monitoring window")
        first = int(math.floor(elapsed_h))
        hours = [first] + [h for h in step_hours_list(total, step) if h > first]
        run = SequenceRun(data, mode="live", hours=total, step_hours=step, settings=s, toolkit=tk,
                          memory=self.memory, store=self.store, budget=self.budget, refresh=fetch)
        try:
            with self.compute:
                run.step(hours[0])
        except AgentSkip as skip:
            run.fail()
            self.feed.mark(usgs_id, "skipped", reason=str(skip))
            raise
        except BaseException:
            run.fail()
            raise
        self.feed.mark(usgs_id, "planned", event_id=data.event_id)
        with self._live_lock:
            self._live[data.event_id] = LiveSequence(run, hours[1:], t0, usgs_id)
        if not hours[1:]:
            self._finish_live(data.event_id)
        return dict(event_id=data.event_id, steps=1)

    # ------------------------------------------------------------------ live mode (scheduler thread)
    def advance_live(self) -> None:
        """Run every live check that is due. A failing sequence is marked failed; the others go on."""
        with self._live_lock:
            items = list(self._live.items())
        now = self.clock()
        for event_id, live in items:
            try:
                while live.hours and now >= live.t0 + live.hours[0] * HOUR:
                    hour = live.hours.pop(0)
                    with self.compute:
                        live.run.step(hour)
                if not live.hours:
                    self._finish_live(event_id)
            except Exception:
                log.exception("live sequence %s failed", event_id)
                live.run.fail()
                with self._live_lock:
                    self._live.pop(event_id, None)

    def _finish_live(self, event_id: str) -> None:
        with self._live_lock:
            live = self._live.pop(event_id, None)
        if live is not None:
            live.run.finish()

    def live_running(self) -> list[str]:
        with self._live_lock:
            return list(self._live)

    def watch_feed(self) -> None:
        """One check of the feed in live mode: start at most one new qualifying earthquake."""
        s = self.settings.values()
        if not s["live_enabled"] or self.jobs is None:
            return
        try:
            quakes, _ = self.feed.quakes()
        except FeedDown:
            return                                        # logged by the feed; try again next time
        for quake in quakes:
            if self.feed.reason_not_to_start(quake, s) is not None:
                continue
            if self.feed.started_last_hour() >= int(s["max_plans_per_hour"]):
                self.feed.mark(quake["usgs_id"], "waiting", reason="hourly plan limit reached")
                continue
            try:
                job = self.jobs.submit(quake["usgs_id"], "sequence", dict(mode="live", usgs_id=quake["usgs_id"]))
            except (JobRunning, RateLimited):
                return                                    # busy: the next check tries again
            self.feed.mark(quake["usgs_id"], "starting", job_id=job["job_id"])
            return

    def tick(self) -> None:
        for task in (self.advance_live, self.watch_feed):
            try:
                task()
            except Exception:
                log.exception("scheduler task %s failed", task.__name__)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()

        def loop():
            while not self._stop.wait(self.poll_s):
                self.tick()
        self._thread = threading.Thread(target=loop, name="quakenet-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread = None

    # ------------------------------------------------------------------ feed and trigger (request threads)
    def feed_snapshot(self) -> dict:
        try:
            return self.feed.snapshot(self.settings.values())
        except FeedDown:
            raise FeedUnavailable("The USGS feed is not reachable right now. Try again in a minute.") from None

    def trigger(self, usgs_id: str) -> dict:
        if not USGS_ID.fullmatch(usgs_id or ""):
            raise InvalidInput("usgs_id must be 4 to 20 lowercase letters or digits.")
        try:
            quake = self.feed.find(usgs_id)
        except FeedDown:
            raise FeedUnavailable("The USGS feed is not reachable right now. Try again in a minute.") from None
        if quake is None:
            raise NotFound("This earthquake is not in the USGS feed of the past day.")
        reason = self.feed.reason_not_to_start(quake, self.settings.values())
        if reason:
            raise InvalidInput(f"Not started: {reason}.")
        job = self.jobs.submit(usgs_id, "sequence", dict(mode="live", usgs_id=usgs_id))
        self.feed.mark(usgs_id, "starting", job_id=job["job_id"])
        return job

    # ------------------------------------------------------------------ noise study (cached)
    def noise(self) -> dict:
        def build() -> dict:
            study = self._noise
            if study is None:
                try:
                    from src.noise import noise_study as study
                except ImportError:
                    raise NotBuilt("The noise study is not built yet.") from None
            with self.compute:
                return study()
        return self._cache.get("noise", build)


def _timestamp(t) -> float:
    if isinstance(t, datetime):
        return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp()
    return datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
