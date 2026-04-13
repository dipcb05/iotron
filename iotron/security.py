"""Security helpers for the IoTron API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from .secrets import available_secret_sources, load_secret
from .storage import is_token_revoked, list_rbac_policies


@dataclass(frozen=True)
class SecuritySettings:
    api_key: str | None
    allowed_origins: list[str]
    requests_per_minute: int
    bearer_secret: str
    previous_bearer_secret: str | None
    token_ttl_seconds: int
    device_token_ttl_seconds: int
    oidc_issuer: str | None
    oidc_audience: str | None


def load_security_settings() -> SecuritySettings:
    origins = os.getenv("IOTRON_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
    bearer_secret = load_secret("IOTRON_BEARER_SECRET", os.getenv("IOTRON_API_KEY") or "iotron-dev-secret")
    return SecuritySettings(
        api_key=os.getenv("IOTRON_API_KEY") or None,
        allowed_origins=[item.strip() for item in origins.split(",") if item.strip()],
        requests_per_minute=int(os.getenv("IOTRON_RATE_LIMIT_PER_MINUTE", "120")),
        bearer_secret=bearer_secret or "iotron-dev-secret",
        previous_bearer_secret=load_secret("IOTRON_PREVIOUS_BEARER_SECRET"),
        token_ttl_seconds=int(os.getenv("IOTRON_TOKEN_TTL_SECONDS", "3600")),
        device_token_ttl_seconds=int(os.getenv("IOTRON_DEVICE_TOKEN_TTL_SECONDS", "86400")),
        oidc_issuer=os.getenv("IOTRON_OIDC_ISSUER") or None,
        oidc_audience=os.getenv("IOTRON_OIDC_AUDIENCE") or None,
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:;"
        )
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


def issue_token(
    subject: str,
    role: str,
    ttl_seconds: int,
    *,
    device_id: str | None = None,
    scopes: list[str] | None = None,
) -> str:
    settings = load_security_settings()
    payload = {
        "sub": subject,
        "role": role,
        "tenant_id": "default",
        "device_id": device_id,
        "scopes": scopes or [],
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
        "jti": secrets.token_hex(8),
    }
    return _encode_token(payload, settings.bearer_secret)


def verify_token(token: str) -> dict[str, Any]:
    settings = load_security_settings()
    for secret in (settings.bearer_secret, settings.previous_bearer_secret):
        if not secret:
            continue
        payload = _decode_token(token, secret)
        if payload is None:
            continue
        if payload["exp"] < int(time.time()):
            raise HTTPException(status_code=401, detail="Token expired")
        if is_token_revoked(payload["jti"]):
            raise HTTPException(status_code=401, detail="Token revoked")
        return payload
    raise HTTPException(status_code=401, detail="Invalid bearer token")


def issue_operator_token(subject: str, role: str = "admin") -> str:
    settings = load_security_settings()
    return issue_token(subject=subject, role=role, ttl_seconds=settings.token_ttl_seconds)


def issue_device_token(device_id: str) -> str:
    settings = load_security_settings()
    return issue_token(
        subject=device_id,
        role="device",
        ttl_seconds=settings.device_token_ttl_seconds,
        device_id=device_id,
        scopes=["telemetry:write", "device:heartbeat"],
    )


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = load_security_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


async def require_operator(x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    settings = load_security_settings()
    if settings.api_key and x_api_key == settings.api_key:
        return {"sub": "api-key", "role": "admin", "auth_type": "api_key"}
    token = _extract_bearer_token(authorization)
    payload = verify_token(token)
    if payload.get("role") not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Operator role required")
    ensure_permission(payload, "devices:write")
    payload["auth_type"] = "bearer"
    return payload


async def require_device_identity(
    authorization: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
) -> dict[str, Any]:
    token = x_device_token or _extract_bearer_token(authorization)
    payload = verify_token(token)
    if payload.get("role") != "device" or not payload.get("device_id"):
        raise HTTPException(status_code=403, detail="Device token required")
    ensure_permission(payload, "telemetry:write")
    payload["auth_type"] = "device"
    return payload


def ensure_permission(identity: dict[str, Any], permission: str) -> None:
    policies = {item["role"]: set(item["permissions"]) for item in list_rbac_policies()}
    granted = policies.get(identity.get("role"), set())
    if "*" in granted or permission in granted:
        return
    if permission in set(identity.get("scopes", [])):
        return
    raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")


def security_metadata() -> dict[str, Any]:
    settings = load_security_settings()
    return {
        "auth_modes": ["api_key", "bearer_operator", "bearer_device"],
        "secret_sources": available_secret_sources(),
        "oidc": {
            "issuer": settings.oidc_issuer,
            "audience": settings.oidc_audience,
            "configured": bool(settings.oidc_issuer and settings.oidc_audience),
        },
    }


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def _encode_token(payload: dict[str, Any], secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
    signature = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _decode_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    padding = "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(body + padding).decode("utf-8"))
