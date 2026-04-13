"""Persistence helpers for project config and package registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


CONFIG_PATH = project_root() / "config.json"
PACKAGE_DB_PATH = project_root() / "vendor" / "installed_packages.db"
RUNTIME_STATE_PATH = project_root() / "vendor" / "runtime_state.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "project": "IoTron",
    "version": "0.1.0",
    "selected_board": None,
    "enabled_protocols": [],
    "enabled_networks": [],
    "features": {
        "web_dashboard": False,
        "fastapi": True,
        "ai_assistant": True,
    },
    "paths": {
        "packages_db": "vendor/installed_packages.db",
    },
}

DEFAULT_PACKAGE_DB: dict[str, Any] = {"packages": []}
DEFAULT_RUNTIME_STATE: dict[str, Any] = {"devices": [], "telemetry": []}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists() or path.read_text(encoding="utf-8").strip() == "":
        _ensure_parent(path)
        _write_json(path, default)
        return json.loads(json.dumps(default))
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_config() -> dict[str, Any]:
    return _read_json(CONFIG_PATH, DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    _write_json(CONFIG_PATH, config)


def load_packages() -> dict[str, Any]:
    return _read_json(PACKAGE_DB_PATH, DEFAULT_PACKAGE_DB)


def save_packages(payload: dict[str, Any]) -> None:
    _write_json(PACKAGE_DB_PATH, payload)


def load_runtime_state() -> dict[str, Any]:
    return _read_json(RUNTIME_STATE_PATH, DEFAULT_RUNTIME_STATE)


def save_runtime_state(payload: dict[str, Any]) -> None:
    _write_json(RUNTIME_STATE_PATH, payload)
