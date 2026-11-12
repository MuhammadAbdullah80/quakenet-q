"""Request and response shapes of docs/API.md."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, create_model

from src.agent.settings import BOOL_KEYS, DEFAULTS, INTEGER_KEYS, LIMITS


# ------------------------------------------------------------------------------- requests
class QaoaJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["qaoa"]
    reps: int = Field(1, ge=1, le=5)
    seed: int = Field(0, ge=0, le=9999)
    shots: int = Field(1024, ge=128, le=4096)
    lam: float = Field(150.0, ge=0, le=1000)


class SequenceJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["sequence"]
    hours: Optional[int] = Field(None, ge=6, le=168)
    step_hours: Optional[int] = Field(None, ge=1, le=12)


JobRequest = Annotated[Union[QaoaJobRequest, SequenceJobRequest], Field(discriminator="kind")]


def _settings_field(key: str):
    if key in BOOL_KEYS:
        return (Optional[bool], None)
    lo, hi = LIMITS[key]
    if key in INTEGER_KEYS:
        return (Optional[int], Field(None, ge=lo, le=hi))
    return (Optional[float], Field(None, ge=lo, le=hi, allow_inf_nan=False))


# Any subset of the editable settings. Unknown keys, wrong types and out-of-range values are
# rejected here, and again by src.agent.settings.check (which also refuses null).
SettingsUpdate = create_model("SettingsUpdate", __config__=ConfigDict(extra="forbid", strict=True),
                              **{key: _settings_field(key) for key in DEFAULTS})


# ------------------------------------------------------------------------------- v1 responses
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
    kind: Literal["benchmark", "live"]
    usgs_id: str
    lat: float
    lon: float


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
    lat: float
    lon: float


class Grid(BaseModel):
    lat0: float
    lon0: float


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
    grid: Grid
    feasibility_checked: bool


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
    objective: Literal["cvar", "mean"] = "mean"     # records written before v2 lack these two fields
    warm_start: bool = False


class SequenceResult(BaseModel):
    event_id: str
    steps: int


class JobSummary(BaseModel):
    job_id: str
    kind: str
    event_id: str
    status: Literal["queued", "running", "done", "failed"]
    created_utc: str
    finished_utc: str | None
    error: str | None


class Job(JobSummary):
    result: QaoaResult | SequenceResult | None


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


# ------------------------------------------------------------------------------- v2: the agent
class AgentSettingsOut(BaseModel):
    trigger_magnitude: float
    station_radius_km: float
    sensors: int
    candidates: int
    risk_weight: float
    move_cost: float
    monitor_interval_hours: int
    monitor_hours: int
    drift_centroid_km: float
    drift_score_drop: float
    min_real_aftershocks: int
    qaoa_layers: int
    shots: int
    hearing_range: bool
    live_enabled: bool
    max_plans_per_hour: int
    limits: dict[str, list[float]]
    updated_utc: str


class FeedQuake(BaseModel):
    usgs_id: str
    place: str
    magnitude: float
    time_utc: str
    lat: float
    lon: float
    depth_km: float
    would_trigger: bool
    status: Literal["below_threshold", "pending", "skipped", "planned"]
    reason: str | None
    event_id: str | None


class FeedOut(BaseModel):
    retrieved_utc: str
    source_url: str
    threshold: float
    live_enabled: bool
    quakes: list[FeedQuake]


class LatLon(BaseModel):
    lat: float
    lon: float


class XY(BaseModel):
    x: float
    y: float


class Move(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    from_: int = Field(alias="from")
    to: int


class StepPlan(BaseModel):
    sites: list[int]
    risk: list[float]
    objective: float
    exact_rank: int
    quantum_agreed: bool
    retries: int
    p_opt_per_shot: float
    moves: list[Move]
    expected_error_km: float
    expert_rule_error_km: float
    seconds: float


class Step(BaseModel):
    hour: int
    stage: Literal["first_plan", "check", "replan"]
    aftershocks_real: int
    aftershocks_used: int
    synthetic: bool
    centroid: XY
    centroid_shift_km: float
    predicted_score: float | None
    realised_score: float | None
    score_drop: float | None
    drift: bool
    drift_reason: str | None
    sites: list[int]
    plan: StepPlan | None


class SequenceSettings(BaseModel):
    sensors: int
    candidates: int
    risk_weight: float
    move_cost: float
    drift_centroid_km: float
    drift_score_drop: float


class SequenceCandidate(BaseModel):
    id: int
    x: float
    y: float
    lat: float
    lon: float
    backups: list[LatLon]


class SequenceOut(BaseModel):
    event_id: str
    mode: Literal["replay", "live"]
    status: Literal["running", "done", "failed"]
    hours_done: int
    hours_total: int
    started_utc: str
    finished_utc: str | None
    settings: SequenceSettings
    grid: Grid
    feasibility_checked: bool
    mainshock: Mainshock
    stations: list[Station]
    candidates: list[SequenceCandidate]
    aftershocks: list[list[float]]
    steps: list[Step]
    current_sites: list[int]
    plans_made: int
    moves_total: int


class PlanSite(BaseModel):
    id: int
    x: float
    y: float
    lat: float
    lon: float
    risk: float
    single_gain: float
    reason: str
    backups: list[LatLon]


class PlanOut(BaseModel):
    event_id: str
    stage: Literal["first_plan", "replan"]
    hour: int
    created_utc: str
    sites: list[PlanSite]
    moves: list[Move]
    objective: float
    exact_rank: int
    quantum_agreed: bool
    p_opt_per_shot: float
    expected_error_km: float
    expert_rule_error_km: float
    confidence: Literal["high", "medium", "low", "unrated"]
    feasibility_checked: bool


class AngleSet(BaseModel):
    key: str
    sensors: int
    candidates: int
    layers: int
    count: int
    median: list[float]


class ModelWeight(BaseModel):
    name: str
    weight: float


class TrackEntry(BaseModel):
    event_id: str
    hour: int
    stage: str
    predicted_score: float
    realised_score: float
    error: float | None


class MemoryOut(BaseModel):
    angles: list[AngleSet]
    model_weights: list[ModelWeight]
    track_record: list[TrackEntry]
    confidence: Literal["high", "medium", "low", "unrated"]
    sequences: int


class NoiseInstance(BaseModel):
    n: int
    k: int
    layers: int
    event_id: str


class NoisePoint(BaseModel):
    gate_error: float
    p_best: float
    valid: float


class NoiseOut(BaseModel):
    instance: NoiseInstance
    points: list[NoisePoint]
    uniform_p_best: float
    note: str
