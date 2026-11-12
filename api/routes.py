"""Routes of docs/API.md. Thin: check the rate limit, call a service, return its result."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request

from . import API_VERSION, schemas
from .errors import RateLimited
from .security import client_ip


def limit(bucket: str):
    def check(request: Request) -> None:
        wait = request.app.state.limiter.hit(bucket, client_ip(request))
        if wait:
            raise RateLimited("Too many requests. Try again later.", retry_after=wait)
    return Depends(check)


Lam = Annotated[float, Query(ge=0, le=1000, description="Information units one unit of access risk must buy")]
UsgsId = Annotated[str, Path(pattern=r"^[a-z0-9]{4,20}$")]

router = APIRouter(prefix="/api/v1")
read = APIRouter(dependencies=[limit("read")])
create = APIRouter(dependencies=[limit("job")])


# ------------------------------------------------------------------------------- v1
@read.get("/health", response_model=schemas.Health)
def health(request: Request):
    return dict(status="ok", version=API_VERSION, region=request.app.state.settings.region,
                time_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


@read.get("/events", response_model=schemas.Events)
def events(request: Request):
    return dict(events=request.app.state.registry.list())


@read.get("/events/{event_id}/instance", response_model=schemas.InstanceOut)
def instance(event_id: str, request: Request):
    return request.app.state.science.instance(event_id)


@read.get("/events/{event_id}/scoring", response_model=schemas.Scoring)
def scoring(event_id: str, request: Request, lam: Lam = 150.0):
    return request.app.state.science.scoring(event_id, lam)


@read.get("/events/{event_id}/baselines", response_model=schemas.Baselines)
def baselines(event_id: str, request: Request, lam: Lam = 150.0):
    return request.app.state.science.baselines(event_id, lam)


@read.get("/jobs", response_model=schemas.Jobs)
def list_jobs(request: Request):
    return dict(jobs=request.app.state.jobs.list())


@read.get("/jobs/{job_id}", response_model=schemas.Job)
def get_job(job_id: str, request: Request):
    return request.app.state.jobs.get(job_id)


@read.get("/system", response_model=schemas.System)
def system(request: Request):
    return dict(request.app.state.jobs.stats(), sources=request.app.state.registry.sources())


@create.post("/events/{event_id}/jobs", status_code=202, response_model=schemas.JobAccepted)
def create_job(event_id: str, body: Annotated[schemas.JobRequest, Body()], request: Request):
    request.app.state.registry.get(event_id)
    if body.kind == "sequence":
        params = request.app.state.agent.sequence_params(body.hours, body.step_hours)
    else:
        params = body.model_dump(exclude={"kind"})
    return request.app.state.jobs.submit(event_id, body.kind, params)


# ------------------------------------------------------------------------------- v2: the agent
@read.get("/settings", response_model=schemas.AgentSettingsOut)
def get_settings(request: Request):
    return request.app.state.agent.get_settings()


@create.put("/settings", response_model=schemas.AgentSettingsOut)
def put_settings(body: schemas.SettingsUpdate, request: Request):
    return request.app.state.agent.put_settings(body.model_dump(exclude_unset=True))


@read.get("/feed", response_model=schemas.FeedOut)
def feed(request: Request):
    return request.app.state.agent.feed_snapshot()


@create.post("/feed/{usgs_id}/trigger", status_code=202, response_model=schemas.JobAccepted)
def trigger(usgs_id: UsgsId, request: Request):
    return request.app.state.agent.trigger(usgs_id)


@read.get("/events/{event_id}/sequence", response_model=schemas.SequenceOut)
def sequence(event_id: str, request: Request):
    return request.app.state.agent.sequence(event_id)


@read.get("/events/{event_id}/plan", response_model=schemas.PlanOut)
def plan(event_id: str, request: Request):
    return request.app.state.agent.plan(event_id)


@read.get("/memory", response_model=schemas.MemoryOut)
def memory(request: Request):
    return request.app.state.agent.get_memory()


@read.get("/noise", response_model=schemas.NoiseOut)
def noise(request: Request):
    return request.app.state.agent.noise()


router.include_router(read)
router.include_router(create)
