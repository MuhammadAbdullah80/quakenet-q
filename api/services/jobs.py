"""Job runner: one worker thread, one job at a time, records kept as JSON files.

A record is written when a job is created and again on every status change, so the job list
survives a restart. A job that was queued or running when the server stopped is marked failed.
"""
from __future__ import annotations

import json
import logging
import math
import os
import queue
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..errors import JobRunning, NotFound, RateLimited

log = logging.getLogger("quakenet.api")

JOB_ID = re.compile(r"[0-9a-f]{6,32}")
STATUSES = ("queued", "running", "done", "failed")
PUBLIC = ("job_id", "kind", "event_id", "status", "created_utc", "finished_utc", "error")
LIST_LIMIT = 50
MAX_RECORDS = 500          # older records are deleted from disk
HOUR = 3600.0
GENERIC_FAILURE = "The job failed. See the server log for details."
INTERRUPTED = "The server restarted before this job finished."


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp(iso: str) -> float:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


class JobService:
    def __init__(self, jobs_dir: Path, execute: Callable[[str, dict], dict], hourly_cap: int,
                 clock: Callable[[], float] = time.time):
        self._dir, self._execute, self._cap, self._clock = Path(jobs_dir), execute, hourly_cap, clock
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._queue: queue.Queue = queue.Queue()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load()
        self._worker = threading.Thread(target=self._work, name="quakenet-jobs", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------ public
    def submit(self, event_id: str, kind: str, params: dict) -> dict:
        now = self._clock()
        with self._lock:
            if any(j["status"] in ("queued", "running") for j in self._jobs.values()):
                raise JobRunning("A job is already running. Wait for it to finish.")
            recent = sorted(j["created_ts"] for j in self._jobs.values() if j["created_ts"] > now - HOUR)
            if len(recent) >= self._cap:
                wait = math.ceil(recent[len(recent) - self._cap] + HOUR - now)
                raise RateLimited("The hourly job limit has been reached.", retry_after=wait)
            job_id = secrets.token_hex(3)
            while job_id in self._jobs:
                job_id = secrets.token_hex(3)
            job = dict(job_id=job_id, kind=kind, event_id=event_id, status="queued", created_utc=_iso(now),
                       finished_utc=None, error=None, result=None, params=dict(params), created_ts=now)
            self._save(job)                       # an OSError here fails the request, before anything runs
            self._jobs[job_id] = job
            self._prune()
        self._queue.put(job_id)
        return dict(job_id=job_id, status="queued")

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise NotFound("Unknown job.")
            return {k: job[k] for k in PUBLIC + ("result",)}

    def list(self) -> list[dict]:
        with self._lock:
            newest = sorted(self._jobs.values(), key=lambda j: j["created_ts"], reverse=True)[:LIST_LIMIT]
            return [{k: j[k] for k in PUBLIC} for j in newest]

    def stats(self) -> dict:
        now = self._clock()
        with self._lock:
            jobs = list(self._jobs.values())
        return dict(jobs_running=sum(j["status"] == "running" for j in jobs),
                    jobs_last_hour=sum(j["created_ts"] > now - HOUR for j in jobs),
                    job_hourly_cap=self._cap)

    def close(self) -> None:
        self._queue.put(None)

    # ------------------------------------------------------------------ worker
    def _work(self) -> None:
        while True:
            job_id = self._queue.get()
            if job_id is None:
                return
            try:
                job = self._update(job_id, status="running")
                result = self._execute(job["event_id"], dict(job["params"]))
                json.dumps(result)                # a result that cannot be stored is a failure
                self._update(job_id, status="done", result=result, finished_utc=_iso(self._clock()))
            except Exception:                     # full detail to the log, generic text to the client
                log.exception("job %s failed", job_id)
                try:
                    self._update(job_id, status="failed", error=GENERIC_FAILURE, finished_utc=_iso(self._clock()))
                except Exception:
                    log.exception("could not record the failure of job %s", job_id)

    def _update(self, job_id: str, **changes) -> dict:
        with self._lock:
            job = self._jobs[job_id]
            job.update(changes)
            try:
                self._save(job)
            except OSError:
                log.exception("could not write the record of job %s", job_id)
            return dict(job)

    # ------------------------------------------------------------------ storage
    def _path(self, job_id: str) -> Path:
        if not JOB_ID.fullmatch(job_id):          # ids are generated here; this guards the file name anyway
            raise ValueError("bad job id")
        return self._dir / f"{job_id}.json"

    def _save(self, job: dict) -> None:
        path = self._path(job["job_id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, indent=1), encoding="utf-8")
        os.replace(tmp, path)                     # atomic: a crash never leaves half a record

    def _prune(self) -> None:
        extra = len(self._jobs) - MAX_RECORDS
        if extra <= 0:
            return
        for job in sorted(self._jobs.values(), key=lambda j: j["created_ts"])[:extra]:
            if job["status"] in ("done", "failed"):
                del self._jobs[job["job_id"]]
                try:
                    self._path(job["job_id"]).unlink(missing_ok=True)
                except OSError:
                    log.exception("could not delete the record of job %s", job["job_id"])

    def _load(self) -> None:
        for path in sorted(self._dir.glob("*.json")):
            try:
                job = self._parse(json.loads(path.read_text(encoding="utf-8")), path.stem)
            except (OSError, ValueError, KeyError, TypeError):
                log.warning("skipping unreadable job record %s", path.name)
                continue
            if job["status"] in ("queued", "running"):
                job.update(status="failed", error=INTERRUPTED, finished_utc=_iso(self._clock()))
                try:
                    self._save(job)
                except OSError:
                    log.exception("could not write the record of job %s", job["job_id"])
            self._jobs[job["job_id"]] = job
        self._prune()

    @staticmethod
    def _parse(raw: dict, stem: str) -> dict:
        job = {k: raw[k] for k in PUBLIC}
        if job["job_id"] != stem or not JOB_ID.fullmatch(stem) or job["status"] not in STATUSES:
            raise ValueError("bad record")
        for key in ("kind", "event_id", "created_utc"):
            if not isinstance(job[key], str):
                raise ValueError("bad record")
        for key in ("finished_utc", "error"):
            if job[key] is not None and not isinstance(job[key], str):
                raise ValueError("bad record")
        result, params = raw.get("result"), raw.get("params") or {}
        if (result is not None and not isinstance(result, dict)) or not isinstance(params, dict):
            raise ValueError("bad record")
        ts = raw.get("created_ts")
        created_ts = float(ts) if isinstance(ts, (int, float)) else _timestamp(job["created_utc"])
        return dict(job, result=result, params=params, created_ts=created_ts)
