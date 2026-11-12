"""Request and response shapes of docs/API.md."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["qaoa"]
    reps: int = Field(1, ge=1, le=5)
    seed: int = Field(0, ge=0, le=9999)
    shots: int = Field(1024, ge=128, le=4096)
    lam: float = Field(150.0, ge=0, le=1000)


class Health(BaseModel):
    status: str
    version: str
    region: str
    time_utc: str


class Event(BaseModel):
    id: str
    name: str
    magnitude: float
    time_utc: str
    region: str
    available: bool


class Events(BaseModel):
    events: list[Event]


class Mainshock(BaseModel):
    x: float
    y: float
    depth: float


class Station(BaseModel):
    name: str
    x: float
    y: float


class Candidate(BaseModel):
    id: int
    x: float
    y: float
    risk: float


class InstanceOut(BaseModel):
    event_id: str
    n: int
    k: int
    decision_hours: int
    mainshock: Mainshock
    design_events: list[list[float]]
    valid_events: list[list[float]]
    stations: list[Station]
    candidates: list[Candidate]


class Fidelity(BaseModel):
    order: int
    terms: int
    spearman: float
    max_abs_error: float
    rank_of_its_optimum: int


class ScoredNetwork(BaseModel):
    sites: list[int]
    objective: float
    risk: float
    blur_km: float
    rank: int


class Scoring(BaseModel):
    lam: float
    feasible_networks: int
    fidelity: list[Fidelity]
    exact_optimum: list[int]
    top_networks: list[ScoredNetwork]


class NoNewSensors(BaseModel):
    blur_km: float
    loc_error_mean_km: float


class Method(BaseModel):
    name: str
    sites: list[int]
    objective: float
    rank: int
    risk: float
    blur_km: float
    loc_error_mean_km: float


class Baselines(BaseModel):
    lam: float
    no_new_sensors: NoNewSensors
    methods: list[Method]


class JobAccepted(BaseModel):
    job_id: str
    status: Literal["queued"]


class CountedNetwork(BaseModel):
    sites: list[int]
    count: int
    objective: float
    rank: int


class FinalNetwork(BaseModel):
    sites: list[int]
    objective: float
    rank: int


class QaoaResult(BaseModel):
    reps: int
    seed: int
    shots: int
    lam: float
    seconds: float
    ratio: float
    p_opt: float
    uniform_p_opt: float
    feasible: float
    depth: int
    gates: int
    evaluations: int
    exact_optimum: list[int]
    top_counts: list[CountedNetwork]
    final: FinalNetwork
    quantum_agreed: bool


class JobSummary(BaseModel):
    job_id: str
    kind: str
    event_id: str
    status: Literal["queued", "running", "done", "failed"]
    created_utc: str
    finished_utc: str | None
    error: str | None


class Job(JobSummary):
    result: QaoaResult | None


class Jobs(BaseModel):
    jobs: list[JobSummary]


class Source(BaseModel):
    name: str
    cached: bool
    retrieved_utc: str | None
    url: str


class System(BaseModel):
    jobs_running: int
    jobs_last_hour: int
    job_hourly_cap: int
    sources: list[Source]
