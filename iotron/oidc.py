"""OIDC and external IAM integration helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

def oidc_metadata() -> dict[str, Any]:
    issuer = os.getenv("IOTRON_OIDC_ISSUER")
    audience = os.getenv("IOTRON_OIDC_AUDIENCE")
    return {
        "issuer": issuer,
        "audience": audience,
        "discovery_url": f"{issuer.rstrip('/')}/.well-known/openid-configuration" if issuer else None,
        "role_claim": os.getenv("IOTRON_OIDC_ROLE_CLAIM", "role"),
        "tenant_claim": os.getenv("IOTRON_OIDC_TENANT_CLAIM", "tenant_id"),
        "configured": bool(issuer and audience),
        "jwks_url": os.getenv("IOTRON_OIDC_JWKS_URL"),
        "shared_secret_configured": bool(os.getenv("IOTRON_OIDC_SHARED_SECRET")),
    }


def fetch_discovery_document(timeout: float = 5.0) -> dict[str, Any]:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover
        raise ValueError("OIDC discovery requires 'httpx' to be installed") from exc
    metadata = oidc_metadata()
    if not metadata["discovery_url"]:
        raise ValueError("OIDC issuer is not configured")
    response = httpx.get(metadata["discovery_url"], timeout=timeout)
    response.raise_for_status()
    return response.json()


def exchange_external_token(token: str) -> dict[str, Any]:
    claims = verify_external_token(token)
    role_claim = os.getenv("IOTRON_OIDC_ROLE_CLAIM", "role")
    tenant_claim = os.getenv("IOTRON_OIDC_TENANT_CLAIM", "tenant_id")
    roles = claims.get(role_claim, [])
    if isinstance(roles, str):
        roles = [roles]
    role = _map_external_roles(roles)
    return {
        "sub": claims["sub"],
        "role": role,
        "tenant_id": claims.get(tenant_claim, "default"),
        "scopes": claims.get("scope", "").split() if isinstance(claims.get("scope"), str) else claims.get("scope", []),
        "issuer": claims.get("iss"),
        "auth_type": "oidc",
        "claims": claims,
    }


def verify_external_token(token: str) -> dict[str, Any]:
    secret = os.getenv("IOTRON_OIDC_SHARED_SECRET")
    if not secret:
        raise ValueError("External OIDC validation requires IOTRON_OIDC_SHARED_SECRET in this environment")
    claims = _decode_hs256_jwt(token, secret)
    metadata = oidc_metadata()
    now = int(time.time())
    if claims.get("exp", now + 1) < now:
        raise ValueError("External token expired")
    if metadata["issuer"] and claims.get("iss") != metadata["issuer"]:
        raise ValueError("External token issuer mismatch")
    audience = claims.get("aud")
    if metadata["audience"]:
        if isinstance(audience, list) and metadata["audience"] not in audience:
            raise ValueError("External token audience mismatch")
        if isinstance(audience, str) and metadata["audience"] != audience:
            raise ValueError("External token audience mismatch")
    return claims


def issue_external_test_token(
    subject: str,
    *,
    role: str = "operator",
    tenant_id: str = "default",
    ttl_seconds: int = 3600,
) -> str:
    metadata = oidc_metadata()
    secret = os.getenv("IOTRON_OIDC_SHARED_SECRET", "iotron-oidc-dev-secret")
    payload = {
        "sub": subject,
        "role": role,
        "tenant_id": tenant_id,
        "iss": metadata["issuer"] or "https://idp.example.test",
        "aud": metadata["audience"] or "iotron",
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    return _encode_hs256_jwt(payload, secret)


def _map_external_roles(roles: list[str]) -> str:
    mapping = {
        "iotron-admin": "admin",
        "iotron-operator": "operator",
        "iotron-viewer": "viewer",
        "iotron-device": "device",
        "admin": "admin",
        "operator": "operator",
        "viewer": "viewer",
        "device": "device",
    }
    for role in roles:
        if role in mapping:
            return mapping[role]
    return "viewer"


def _encode_hs256_jwt(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_part}.{payload_part}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest()
    return f"{message}.{_b64url(signature)}"


def _decode_hs256_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid external token format") from exc
    message = f"{header_part}.{payload_part}"
    expected = _b64url(hmac.new(secret.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature_part):
        raise ValueError("External token signature mismatch")
    header = json.loads(_b64url_decode(header_part).decode("utf-8"))
    if header.get("alg") != "HS256":
        raise ValueError("Unsupported external token algorithm")
    return json.loads(_b64url_decode(payload_part).decode("utf-8"))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
