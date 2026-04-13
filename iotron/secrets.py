"""Secret loading helpers with environment and file-backed providers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _secret_file_path() -> Path | None:
    configured = os.getenv("IOTRON_SECRET_FILE")
    if configured:
        return Path(configured)
    default = Path(__file__).resolve().parent.parent / "vendor" / "secrets.json"
    return default if default.exists() else None


def load_secret(name: str, default: str | None = None) -> str | None:
    env_name = name.upper()
    value = os.getenv(env_name)
    if value is not None:
        return value

    secret_file = _secret_file_path()
    if secret_file and secret_file.exists():
        try:
            payload: dict[str, Any] = json.loads(secret_file.read_text(encoding="utf-8"))
            if name in payload:
                return str(payload[name])
        except json.JSONDecodeError:
            return default
    return default


def available_secret_sources() -> list[str]:
    sources = ["environment"]
    if _secret_file_path():
        sources.append("file")
    return sources
