"""Persistence helpers for project config and SQLite-backed vendor storage."""

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
# Legacy import sources retained for one-way bootstrap from older JSON-backed installs.
PACKAGE_DB_PATH = project_root() / "vendor" / "installed_packages.db"
RUNTIME_STATE_PATH = project_root() / "vendor" / "runtime_state.json"
# Active vendor storage backend.
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

        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rbac_policies (
            role TEXT PRIMARY KEY,
            permissions_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti TEXT PRIMARY KEY,
            revoked_at TEXT NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_channels (
            channel_id TEXT PRIMARY KEY,
            channel_type TEXT NOT NULL,
            target TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            backend TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            result_json TEXT,
            error TEXT,
            submitted_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            claimed_by TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_telemetry_device_recorded_at
        ON telemetry(device_id, recorded_at DESC);

        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
        ON audit_log(created_at DESC);
        """
    )
    _seed_defaults(connection)
    _bootstrap_from_legacy_json(connection)


def _seed_defaults(connection: sqlite3.Connection) -> None:
    tenant_count = connection.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
    if tenant_count == 0:
        connection.execute(
            "INSERT INTO tenants(tenant_id, name, created_at) VALUES (?, ?, datetime('now'))",
            ("default", "Default Tenant"),
        )
    policy_count = connection.execute("SELECT COUNT(*) FROM rbac_policies").fetchone()[0]
    if policy_count == 0:
        defaults = {
            "admin": ["*"],
            "operator": [
                "devices:read",
                "devices:write",
                "telemetry:read",
                "deployments:write",
                "deployments:read",
                "backups:write",
                "audit:read",
            ],
            "viewer": ["devices:read", "telemetry:read", "deployments:read"],
            "device": ["telemetry:write", "device:heartbeat"],
        }
        for role, permissions in defaults.items():
            connection.execute(
                "INSERT INTO rbac_policies(role, permissions_json, updated_at) VALUES (?, ?, datetime('now'))",
                (role, json.dumps(permissions)),
            )


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


def create_tenant(tenant_id: str, name: str, created_at: str) -> dict[str, Any]:
    with _db() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO tenants(tenant_id, name, created_at) VALUES (?, ?, ?)",
            (tenant_id, name, created_at),
        )
    return {"tenant_id": tenant_id, "name": name, "created_at": created_at}


def list_tenants() -> list[dict[str, Any]]:
    with _db() as connection:
        rows = connection.execute("SELECT tenant_id, name, created_at FROM tenants ORDER BY created_at ASC").fetchall()
    return [dict(row) for row in rows]


def set_rbac_policy(role: str, permissions: list[str], updated_at: str) -> dict[str, Any]:
    with _db() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO rbac_policies(role, permissions_json, updated_at) VALUES (?, ?, ?)",
            (role, json.dumps(permissions), updated_at),
        )
    return {"role": role, "permissions": permissions, "updated_at": updated_at}


def list_rbac_policies() -> list[dict[str, Any]]:
    with _db() as connection:
        rows = connection.execute("SELECT role, permissions_json, updated_at FROM rbac_policies ORDER BY role ASC").fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["permissions"] = json.loads(item.pop("permissions_json") or "[]")
        payload.append(item)
    return payload


def revoke_token(jti: str, revoked_at: str, reason: str) -> dict[str, Any]:
    with _db() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO revoked_tokens(jti, revoked_at, reason) VALUES (?, ?, ?)",
            (jti, revoked_at, reason),
        )
    return {"jti": jti, "revoked_at": revoked_at, "reason": reason}


def is_token_revoked(jti: str) -> bool:
    with _db() as connection:
        row = connection.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
    return row is not None


def create_notification_channel(
    channel_id: str,
    channel_type: str,
    target: str,
    enabled: bool,
    metadata: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    with _db() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO notification_channels(
                channel_id, channel_type, target, enabled, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (channel_id, channel_type, target, int(enabled), json.dumps(metadata), created_at),
        )
    return {
        "channel_id": channel_id,
        "channel_type": channel_type,
        "target": target,
        "enabled": enabled,
        "metadata": metadata,
        "created_at": created_at,
    }


def list_notification_channels() -> list[dict[str, Any]]:
    with _db() as connection:
        rows = connection.execute(
            "SELECT channel_id, channel_type, target, enabled, metadata_json, created_at FROM notification_channels ORDER BY created_at ASC"
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        item["enabled"] = bool(item["enabled"])
        payload.append(item)
    return payload


def save_job(record: dict[str, Any]) -> dict[str, Any]:
    with _db() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO jobs(
                job_id, name, backend, status, payload_json, result_json, error,
                submitted_at, updated_at, claimed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["job_id"],
                record["name"],
                record["backend"],
                record["status"],
                json.dumps(record.get("payload", {})),
                json.dumps(record["result"]) if record.get("result") is not None else None,
                record.get("error"),
                record["submitted_at"],
                record["updated_at"],
                record.get("claimed_by"),
            ),
        )
    return record


def get_job_record(job_id: str) -> dict[str, Any] | None:
    with _db() as connection:
        row = connection.execute(
            """
            SELECT job_id, name, backend, status, payload_json, result_json, error, submitted_at, updated_at, claimed_by
            FROM jobs WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json") or "{}")
    item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
    item.pop("result_json", None)
    return item


def list_job_records(limit: int = 100) -> list[dict[str, Any]]:
    with _db() as connection:
        rows = connection.execute(
            """
            SELECT job_id, name, backend, status, payload_json, result_json, error, submitted_at, updated_at, claimed_by
            FROM jobs ORDER BY updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
        item.pop("result_json", None)
        payload.append(item)
    return payload


def claim_next_job(worker_id: str, backend: str = "sqlite") -> dict[str, Any] | None:
    with _db() as connection:
        row = connection.execute(
            """
            SELECT job_id, name, backend, status, payload_json, result_json, error, submitted_at, updated_at, claimed_by
            FROM jobs
            WHERE status = 'queued' AND backend = ?
            ORDER BY submitted_at ASC
            LIMIT 1
            """,
            (backend,),
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE jobs SET status = ?, claimed_by = ?, updated_at = datetime('now') WHERE job_id = ?",
            ("running", worker_id, row["job_id"]),
        )
    return get_job_record(row["job_id"])
