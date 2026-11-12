"""HTTP gateway: shared-secret check, security headers, and a last-resort error barrier."""
from __future__ import annotations

import hmac
import ipaddress
import json
import logging

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request

log = logging.getLogger("quakenet.api")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def client_ip(request: Request) -> str:
    """Client address for rate limiting.

    The API is only reachable through the tunnel, and the Next.js server passes the browser's address
    in X-Client-IP. The header is trusted because this runs after the shared-secret check: whoever
    sets it already holds the token. Anything that is not an IP address is ignored.
    """
    forwarded = request.headers.get("x-client-ip")
    if forwarded:
        try:
            return str(ipaddress.ip_address(forwarded.strip()))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


class GatewayMiddleware:
    """Pure ASGI middleware around the whole app, so even unknown routes need the token."""

    def __init__(self, app, token: str):
        self.app = app
        self._token = token.encode("utf-8")

    def _authorised(self, header: str | None) -> bool:
        scheme, _, presented = (header or "").partition(" ")
        ok_scheme = scheme.lower() == "bearer"
        # always compare, in constant time, so the response time does not reveal which check failed
        return hmac.compare_digest(presented.encode("utf-8"), self._token) and ok_scheme

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def send_with_headers(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers[name] = value
            await send(message)

        async def reply(status: int, code: str, message: str, extra: dict | None = None):
            body = json.dumps(error_body(code, message)).encode("utf-8")
            headers = {"content-type": "application/json", "content-length": str(len(body)), **(extra or {})}
            await send_with_headers({"type": "http.response.start", "status": status,
                                     "headers": [(k.encode(), v.encode()) for k, v in headers.items()]})
            await send_with_headers({"type": "http.response.body", "body": body})

        if not self._authorised(Headers(scope=scope).get("authorization")):
            await reply(401, "UNAUTHORIZED", "Missing or invalid bearer token.", {"www-authenticate": "Bearer"})
            return
        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            # the request line only: headers (and so the token) are never logged
            log.exception("unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if not started:
                await reply(500, "INTERNAL", "Internal error.")
