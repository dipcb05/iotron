"""Persistence helpers for project config and production-oriented local storage."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


CONFIG_PATH = project_root() / "config.json"
PACKAGE_DB_PATH = project_root() / "vendor" / "installed_packages.db"
RUNTIME_STATE_PATH = project_root() / "vendor" / "runtime_state.json"
SQLITE_DB_PATH = project_root() / "vendor" / "iotron_state.db"


DEFAULT_CONFIG: dict[str, Any] = {
    "project": "IoTron",
    "version": "0.3.0",
    "selected_board": None,
    "enabled_protocols": [],
    "enabled_networks": [],
    "features": {
        "web_dashboard": False,
        "fastapi": True,
        "ai_assistant": True,
    },
    "paths": {
        "packages_db": "vendor/iotron_state.db",
    },
}

DEFAULT_PACKAGE_DB: dict[str, Any] = {"packages": []}
DEFAULT_RUNTIME_STATE: dict[str, Any] = {"devices": [], "telemetry": []}

_DB_LOCK = threading.RLock()


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


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    _ensure_parent(SQLITE_DB_PATH)
    with _DB_LOCK:
        connection = sqlite3.connect(SQLITE_DB_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        _migrate(connection)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def _migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS packages (
            name TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            installed_at TEXT NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            board TEXT NOT NULL,
            protocol TEXT,
            network TEXT,
            metadata_json TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            auth_identity TEXT
        );

        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value_json TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            board TEXT NOT NULL,
            artifact TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            rollout_json TEXT NOT NULL,
            rollback_artifact TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_telemetry_device_recorded_at
        ON telemetry(device_id, recorded_at DESC);

        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
        ON audit_log(created_at DESC);
        """
    )
    _bootstrap_from_legacy_json(connection)


def _bootstrap_from_legacy_json(connection: sqlite3.Connection) -> None:
    package_count = connection.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
    if package_count == 0 and PACKAGE_DB_PATH.exists():
        legacy = _read_json(PACKAGE_DB_PATH, DEFAULT_PACKAGE_DB)
        for package in legacy.get("packages", []):
            connection.execute(
                """
                INSERT OR REPLACE INTO packages(name, version, installed_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    package["name"],
                    package.get("version", "latest"),
                    package.get("installed_at", ""),
                    package.get("status", "installed"),
                ),
            )

    device_count = connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    if device_count == 0 and RUNTIME_STATE_PATH.exists():
        legacy = _read_json(RUNTIME_STATE_PATH, DEFAULT_RUNTIME_STATE)
        for device in legacy.get("devices", []):
            connection.execute(
                """
                INSERT OR REPLACE INTO devices(
                    device_id, board, protocol, network, metadata_json, registered_at, last_seen, auth_identity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device["device_id"],
                    device["board"],
                    device.get("protocol"),
                    device.get("network"),
                    json.dumps(device.get("metadata", {})),
                    device.get("registered_at", ""),
                    device.get("last_seen", ""),
                    device.get("auth_identity"),
                ),
            )
        for event in legacy.get("telemetry", []):
            connection.execute(
                """
                INSERT INTO telemetry(device_id, metric, value_json, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event["device_id"],
                    event["metric"],
                    json.dumps(event.get("value")),
                    event["recorded_at"],
                ),
            )


def load_config() -> dict[str, Any]:
    return _read_json(CONFIG_PATH, DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    _write_json(CONFIG_PATH, config)


def load_packages() -> dict[str, Any]:
    with _db() as connection:
        rows = connection.execute(
            "SELECT name, version, installed_at, status FROM packages ORDER BY installed_at ASC"
        ).fetchall()
    return {"packages": [dict(row) for row in rows]}


def save_packages(payload: dict[str, Any]) -> None:
    packages = payload.get("packages", [])
    with _db() as connection:
        connection.execute("DELETE FROM packages")
        connection.executemany(
            """
            INSERT INTO packages(name, version, installed_at, status)
            VALUES (:name, :version, :installed_at, :status)
            """,
            packages,
        )
    _write_json(PACKAGE_DB_PATH, {"packages": packages})


def load_runtime_state() -> dict[str, Any]:
    with _db() as connection:
        device_rows = connection.execute(
            """
            SELECT device_id, board, protocol, network, metadata_json, registered_at, last_seen, auth_identity
            FROM devices
            ORDER BY registered_at ASC
            """
        ).fetchall()
        telemetry_rows = connection.execute(
            """
            SELECT device_id, metric, value_json, recorded_at
            FROM telemetry
            ORDER BY recorded_at ASC
            """
        ).fetchall()
    devices = []
    for row in device_rows:
        payload = dict(row)
        payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
        devices.append(payload)
    telemetry = []
    for row in telemetry_rows:
        payload = dict(row)
        payload["value"] = json.loads(payload.pop("value_json"))
        telemetry.append(payload)
    state = {"devices": devices, "telemetry": telemetry}
    _write_json(RUNTIME_STATE_PATH, state)
    return state


def save_runtime_state(payload: dict[str, Any]) -> None:
    devices = payload.get("devices", [])
    telemetry = payload.get("telemetry", [])
    with _db() as connection:
        connection.execute("DELETE FROM telemetry")
        connection.execute("DELETE FROM devices")
        connection.executemany(
            """
            INSERT INTO devices(
                device_id, board, protocol, network, metadata_json, registered_at, last_seen, auth_identity
            ) VALUES (:device_id, :board, :protocol, :network, :metadata_json, :registered_at, :last_seen, :auth_identity)
            """,
            [
                {
                    "device_id": item["device_id"],
                    "board": item["board"],
                    "protocol": item.get("protocol"),
                    "network": item.get("network"),
                    "metadata_json": json.dumps(item.get("metadata", {})),
                    "registered_at": item["registered_at"],
                    "last_seen": item["last_seen"],
                    "auth_identity": item.get("auth_identity"),
                }
                for item in devices
            ],
        )
        connection.executemany(
            """
            INSERT INTO telemetry(device_id, metric, value_json, recorded_at)
            VALUES (:device_id, :metric, :value_json, :recorded_at)
            """,
            [
                {
                    "device_id": item["device_id"],
                    "metric": item["metric"],
                    "value_json": json.dumps(item.get("value")),
                    "recorded_at": item["recorded_at"],
                }
                for item in telemetry
            ],
        )
    _write_json(RUNTIME_STATE_PATH, payload)


def save_deployment(record: dict[str, Any]) -> None:
    with _db() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO deployments(
                deployment_id, operation, board, artifact, artifact_sha256, stage, status,
                rollout_json, rollback_artifact, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["deployment_id"],
                record["operation"],
                record["board"],
                record["artifact"],
                record["artifact_sha256"],
                record["stage"],
                record["status"],
                json.dumps(record.get("rollout", {})),
                record.get("rollback_artifact"),
                record["created_at"],
                record["updated_at"],
            ),
        )


def list_deployments(limit: int = 100) -> list[dict[str, Any]]:
    with _db() as connection:
        rows = connection.execute(
            """
            SELECT deployment_id, operation, board, artifact, artifact_sha256, stage, status,
                   rollout_json, rollback_artifact, created_at, updated_at
            FROM deployments
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    records = []
    for row in rows:
        payload = dict(row)
        payload["rollout"] = json.loads(payload.pop("rollout_json") or "{}")
        records.append(payload)
    return records


def log_audit_event(
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any],
    created_at: str,
) -> None:
    with _db() as connection:
        connection.execute(
            """
            INSERT INTO audit_log(actor, action, resource_type, resource_id, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (actor, action, resource_type, resource_id, json.dumps(metadata), created_at),
        )


def list_audit_events(limit: int = 100) -> list[dict[str, Any]]:
    with _db() as connection:
        rows = connection.execute(
            """
            SELECT actor, action, resource_type, resource_id, metadata_json, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    events = []
    for row in rows:
        payload = dict(row)
        payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
        events.append(payload)
    return events


def prune_telemetry(retain_latest_per_device: int = 1000) -> int:
    with _db() as connection:
        devices = connection.execute("SELECT device_id FROM devices").fetchall()
        deleted = 0
        for row in devices:
            device_id = row["device_id"]
            ids = connection.execute(
                """
                SELECT id FROM telemetry
                WHERE device_id = ?
                ORDER BY recorded_at DESC
                LIMIT -1 OFFSET ?
                """,
                (device_id, retain_latest_per_device),
            ).fetchall()
            if ids:
                connection.executemany("DELETE FROM telemetry WHERE id = ?", [(item["id"],) for item in ids])
                deleted += len(ids)
    return deleted
