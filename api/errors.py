"""Domain errors raised by the service layer. They carry a contract code, not an HTTP status;
the HTTP layer (main.py) decides the status."""
from __future__ import annotations


class ApiError(Exception):
    code = "INTERNAL"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(ApiError):
    code = "NOT_FOUND"


class JobRunning(ApiError):
    code = "JOB_RUNNING"


class NotBuilt(ApiError):
    code = "NOT_BUILT"


class RateLimited(ApiError):
    code = "RATE_LIMITED"

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))
