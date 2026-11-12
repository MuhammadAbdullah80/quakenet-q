"""Application factory.  Start with:  uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000"""
from __future__ import annotations

import logging
import threading

import re
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.agent.planner import Budget
from src.qaoa_solver import run_xy_qaoa

from . import API_VERSION
from .config import Settings
from .errors import ApiError, RateLimited
from .ratelimit import RateLimiter
from .routes import router
from .security import GatewayMiddleware, error_body
from .services.agent import AgentService
from .services.events import default_registry
from .services.jobs import JobService
from .services.science import ScienceService

log = logging.getLogger("quakenet.api")

STATUS = {"UNAUTHORIZED": 401, "NOT_FOUND": 404, "INVALID_INPUT": 422, "RATE_LIMITED": 429, "JOB_RUNNING": 409,
          "NOT_BUILT": 501, "INTERNAL": 500, "FEED_UNAVAILABLE": 503}
FIELD = re.compile(r"[A-Za-z0-9_]{1,32}")


def _warm(compute: Callable[[], object]) -> None:
    try:
        compute()
    except Exception:                                   # a failed warm-up only means a slower first visit
        log.warning("noise study warm-up failed", exc_info=True)


def create_app(settings: Settings | None = None, solver: Callable | None = None, toolkit=None,
               feed_get: Callable | None = None, noise: Callable | None = None) -> FastAPI:
    """Raises RuntimeError (so the server does not start) if QUAKENET_TOKEN is missing or too short.

    `solver`, `toolkit`, `feed_get` and `noise` replace the real science functions in tests."""
    settings = settings or Settings.from_env()
    solver = solver or run_xy_qaoa

    @lru_cache(maxsize=1)
    def real_toolkit():
        from src.agent.toolkit import default_toolkit
        return default_toolkit(solver)

    toolkit_factory = (lambda: toolkit) if toolkit is not None else real_toolkit
    registry = default_registry(settings.region, toolkit_factory)
    science = ScienceService(registry)
    agent = AgentService(settings.var_dir, registry, toolkit_factory,
                         Budget(restarts=settings.agent_restarts, maxiter=settings.agent_maxiter,
                                loc_events=settings.agent_loc_events),
                         http_get=feed_get, poll_s=settings.feed_poll_s, noise=noise)

    def execute(kind: str, event_id: str, params: dict) -> dict:
        if kind == "sequence":
            return agent.run_sequence_job(event_id, params)
        return science.qaoa(event_id, restarts=settings.qaoa_restarts, maxiter=settings.qaoa_maxiter,
                            solver=solver, **params)

    jobs = JobService(settings.jobs_dir, hourly_cap=settings.hourly_cap, execute=execute)
    agent.jobs = jobs

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.scheduler:
            agent.start()
            # Fill the noise-study cache in the background: computing it takes longer than the
            # console waits for an answer, so the first visitor after a restart would see an error.
            threading.Thread(target=_warm, args=(agent.noise,), name="warm-noise", daemon=True).start()
        yield
        agent.stop()
        jobs.close()

    # No CORS (the browser never calls this API) and no hosted docs page (it would load third-party scripts).
    app = FastAPI(title="QuakeNet-Q API", version=API_VERSION, lifespan=lifespan,
                  openapi_url="/api/v1/openapi.json", docs_url=None, redoc_url=None)
    app.state.settings, app.state.registry, app.state.science, app.state.jobs = settings, registry, science, jobs
    app.state.agent = agent
    app.state.limiter = RateLimiter({"read": settings.read_limit, "job": settings.job_limit})

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimited) else None
        return JSONResponse(error_body(exc.code, exc.message), STATUS[exc.code], headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_: Request, exc: RequestValidationError):
        # Field name and rule only: the rejected value is never echoed back.
        parts = []
        for err in exc.errors()[:5]:
            loc = [str(p) for p in err.get("loc", ())[1:]]
            name = ".".join(p if FIELD.fullmatch(p) else "?" for p in loc) or "body"
            parts.append(f"{name}: {err.get('type', 'invalid')}")
        return JSONResponse(error_body("INVALID_INPUT", "Invalid input (" + "; ".join(parts) + ")."), 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return JSONResponse(error_body("NOT_FOUND", "Not found."), 404)
        if exc.status_code == 405:
            return JSONResponse(error_body("INVALID_INPUT", "Method not allowed."), 405, headers=exc.headers)
        code = "INVALID_INPUT" if 400 <= exc.status_code < 500 else "INTERNAL"
        return JSONResponse(error_body(code, "Request failed."), exc.status_code)

    app.include_router(router)
    app.add_middleware(GatewayMiddleware, token=settings.token)
    return app
