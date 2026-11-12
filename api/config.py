"""Settings. Secrets come from environment variables only and are never logged or printed."""
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
    region: str = "local"
    qaoa_restarts: int = 2                     # optimiser budget: COBYLA starts per job
    qaoa_maxiter: int = 250                    # optimiser budget: steps per start
    read_limit: int = 60                       # requests per minute per client IP
    job_limit: int = 5                         # job creations per minute per client IP
    hourly_cap: int = 30                       # jobs per hour, all clients together

    def __post_init__(self) -> None:
        token = self.token
        if not isinstance(token, str) or len(token) < MIN_TOKEN_LENGTH:
            raise RuntimeError(f"QUAKENET_TOKEN must be set to at least {MIN_TOKEN_LENGTH} characters.")
        if not token.isascii() or not token.isprintable() or " " in token:
            raise RuntimeError("QUAKENET_TOKEN must be printable ASCII without spaces.")
        if not 1 <= self.qaoa_restarts <= 8:
            raise RuntimeError("QUAKENET_QAOA_RESTARTS must be between 1 and 8.")
        if not 1 <= self.qaoa_maxiter <= 1000:
            raise RuntimeError("QUAKENET_QAOA_MAXITER must be between 1 and 1000.")
        if min(self.read_limit, self.job_limit, self.hourly_cap) < 1:
            raise RuntimeError("Rate limits must be positive.")

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        try:
            restarts = int(env.get("QUAKENET_QAOA_RESTARTS", "2"))
            maxiter = int(env.get("QUAKENET_QAOA_MAXITER", "250"))
        except ValueError:
            raise RuntimeError("QUAKENET_QAOA_RESTARTS and QUAKENET_QAOA_MAXITER must be whole numbers.") from None
        return cls(token=env.get("QUAKENET_TOKEN", ""),
                   jobs_dir=Path(env.get("QUAKENET_JOBS_DIR") or ROOT / "var" / "jobs"),
                   region=env.get("QUAKENET_REGION") or "local",
                   qaoa_restarts=restarts, qaoa_maxiter=maxiter)
