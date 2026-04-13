"""Security helpers for the IoTron API."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class SecuritySettings:
    api_key: str | None
    allowed_origins: list[str]
    requests_per_minute: int


def load_security_settings() -> SecuritySettings:
    origins = os.getenv("IOTRON_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
    return SecuritySettings(
        api_key=os.getenv("IOTRON_API_KEY") or None,
        allowed_origins=[item.strip() for item in origins.split(",") if item.strip()],
        requests_per_minute=int(os.getenv("IOTRON_RATE_LIMIT_PER_MINUTE", "120")),
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:;"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._hits[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.requests_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        window.append(now)
        return await call_next(request)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = load_security_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
