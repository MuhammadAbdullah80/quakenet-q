"""Routes of docs/API.md. Thin: check the rate limit, call a service, return its result."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from . import API_VERSION, schemas
from .errors import NotBuilt, RateLimited
from .security import client_ip


def limit(bucket: str):
    def check(request: Request) -> None:
        wait = request.app.state.limiter.hit(bucket, client_ip(request))
        if wait:
            raise RateLimited("Too many requests. Try again later.", retry_after=wait)
    return Depends(check)


Lam = Annotated[float, Query(ge=0, le=1000, description="Information units one unit of access risk must buy")]

router = APIRouter(prefix="/api/v1")
read = APIRouter(dependencies=[limit("read")])


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


@read.get("/events/{event_id}/plan")
@read.get("/events/{event_id}/replay")
def not_built_for_event(event_id: str, request: Request):
    request.app.state.registry.get(event_id)
    raise NotBuilt("Not built yet.")


@read.get("/memory")
def memory():
    raise NotBuilt("Not built yet.")


@router.post("/events/{event_id}/jobs", status_code=202, response_model=schemas.JobAccepted,
             dependencies=[limit("job")])
def create_job(event_id: str, body: schemas.JobRequest, request: Request):
    request.app.state.registry.get(event_id)
    return request.app.state.jobs.submit(event_id, body.kind, body.model_dump(exclude={"kind"}))


router.include_router(read)
