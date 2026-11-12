"""Settings. Secrets come from environment variables only and are never logged or printed.

These are the server's own settings. The settings a scientist edits through the API
(trigger magnitude and so on) live in src/agent/settings.py and var/settings.json.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_TOKEN_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)             # shared secret; repr=False keeps it out of logs
    jobs_dir: Path = ROOT / "var" / "jobs"
    var_dir: Path | None = None                # agent state (settings, memory, sequences, feed); default: jobs_dir/..
    region: str = "local"
    qaoa_restarts: int = 2                     # optimiser budget of a qaoa job: COBYLA starts
    qaoa_maxiter: int = 250                    # optimiser budget of a qaoa job: steps per start
    agent_restarts: int = 4                    # optimiser budget of an agent plan: random starts on a cold start
    agent_maxiter: int = 250                   # optimiser budget of an agent plan: steps per start
    agent_loc_events: int = 100                # aftershocks used for a plan's location-error estimates
    feed_poll_s: float = 60.0                  # scheduler period: live sequences and the feed watcher
    scheduler: bool = True                     # start the scheduler thread with the server
    read_limit: int = 60                       # requests per minute per client IP
    job_limit: int = 5                         # job creations per minute per client IP
    hourly_cap: int = 30                       # jobs per hour, all clients together

    def __post_init__(self) -> None:
        token = self.token
        if not isinstance(token, str) or len(token) < MIN_TOKEN_LENGTH:
            raise RuntimeError(f"QUAKENET_TOKEN must be set to at least {MIN_TOKEN_LENGTH} characters.")
        if not token.isascii() or not token.isprintable() or " " in token:
            raise RuntimeError("QUAKENET_TOKEN must be printable ASCII without spaces.")
        if not 1 <= self.qaoa_restarts <= 8 or not 1 <= self.agent_restarts <= 8:
            raise RuntimeError("QUAKENET_QAOA_RESTARTS and QUAKENET_AGENT_RESTARTS must be between 1 and 8.")
        if not 1 <= self.qaoa_maxiter <= 1000 or not 1 <= self.agent_maxiter <= 1000:
            raise RuntimeError("QUAKENET_QAOA_MAXITER and QUAKENET_AGENT_MAXITER must be between 1 and 1000.")
        if not 5 <= self.agent_loc_events <= 1000:
            raise RuntimeError("QUAKENET_AGENT_LOC_EVENTS must be between 5 and 1000.")
        if not 0.01 <= self.feed_poll_s <= 3600:
            raise RuntimeError("QUAKENET_FEED_POLL_S must be between 0.01 and 3600.")
        if min(self.read_limit, self.job_limit, self.hourly_cap) < 1:
            raise RuntimeError("Rate limits must be positive.")
        if self.var_dir is None:
            object.__setattr__(self, "var_dir", Path(self.jobs_dir).parent)

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ

        def number(name: str, default: str, kind=int):
            try:
                return kind(env.get(name) or default)
            except ValueError:
                raise RuntimeError(f"{name} must be a number.") from None

        var_dir = env.get("QUAKENET_VAR_DIR")
        return cls(token=env.get("QUAKENET_TOKEN", ""),
                   jobs_dir=Path(env.get("QUAKENET_JOBS_DIR") or ROOT / "var" / "jobs"),
                   var_dir=Path(var_dir) if var_dir else None,
                   region=env.get("QUAKENET_REGION") or "local",
                   qaoa_restarts=number("QUAKENET_QAOA_RESTARTS", "2"),
                   qaoa_maxiter=number("QUAKENET_QAOA_MAXITER", "250"),
                   agent_restarts=number("QUAKENET_AGENT_RESTARTS", "4"),
                   agent_maxiter=number("QUAKENET_AGENT_MAXITER", "250"),
                   agent_loc_events=number("QUAKENET_AGENT_LOC_EVENTS", "100"),
                   feed_poll_s=number("QUAKENET_FEED_POLL_S", "60", float))
