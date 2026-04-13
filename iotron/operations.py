"""Operational helpers for jobs, alerts, and backup/restore."""

from __future__ import annotations

import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .observability import log_event, record_metric
from .storage import CONFIG_PATH, SQLITE_DB_PATH, project_root

_EXECUTOR = ThreadPoolExecutor(max_workers=4)
_JOBS_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}


def submit_job(name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    job_id = f"job-{uuid4().hex[:12]}"
    submitted_at = datetime.now(timezone.utc).isoformat()
    future = _EXECUTOR.submit(fn, *args, **kwargs)
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "name": name,
            "status": "queued",
            "submitted_at": submitted_at,
            "future": future,
        }
    record_metric("jobs.submitted", 1)
    log_event("info", "job_submitted", job_id=job_id, name=name)
    return {"job_id": job_id, "name": name, "status": "queued", "submitted_at": submitted_at}


def list_jobs() -> list[dict[str, Any]]:
    with _JOBS_LOCK:
        jobs = []
        for job in _JOBS.values():
            payload = dict(job)
            future = payload.pop("future")
            payload.update(_future_status(future))
            jobs.append(payload)
        return sorted(jobs, key=lambda item: item["submitted_at"], reverse=True)


def get_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        payload = dict(job)
        future = payload.pop("future")
        payload.update(_future_status(future))
        return payload


def create_backup() -> dict[str, Any]:
    backup_dir = project_root() / "vendor" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir = backup_dir / stamp
    target_dir.mkdir(exist_ok=True)

    copied = []
    for path in (CONFIG_PATH, SQLITE_DB_PATH):
        if path.exists():
            destination = target_dir / path.name
            shutil.copy2(path, destination)
            copied.append(str(destination))

    record_metric("backups.created", 1)
    log_event("info", "backup_created", backup_dir=str(target_dir), files=copied)
    return {"backup_id": stamp, "directory": str(target_dir), "files": copied}


def restore_backup(backup_id: str) -> dict[str, Any]:
    backup_dir = project_root() / "vendor" / "backups" / backup_id
    if not backup_dir.exists():
        raise ValueError(f"Backup '{backup_id}' was not found")

    restored = []
    for source, destination in ((backup_dir / CONFIG_PATH.name, CONFIG_PATH), (backup_dir / SQLITE_DB_PATH.name, SQLITE_DB_PATH)):
        if source.exists():
            shutil.copy2(source, destination)
            restored.append(str(destination))

    record_metric("backups.restored", 1)
    log_event("warning", "backup_restored", backup_id=backup_id, files=restored)
    return {"backup_id": backup_id, "restored_files": restored}


def list_backups() -> list[dict[str, Any]]:
    backup_dir = project_root() / "vendor" / "backups"
    if not backup_dir.exists():
        return []
    backups = []
    for item in sorted(backup_dir.iterdir(), reverse=True):
        if item.is_dir():
            backups.append(
                {
                    "backup_id": item.name,
                    "directory": str(item),
                    "files": sorted(path.name for path in item.iterdir() if path.is_file()),
                }
            )
    return backups


def generate_alerts(devices: list[dict[str, Any]], deployments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for device in devices:
        if not device.get("last_seen"):
            alerts.append({"severity": "warning", "type": "device", "message": f"{device['device_id']} has never checked in"})
    for deployment in deployments:
        if deployment.get("status") in {"failed", "failed_preflight", "blocked"}:
            alerts.append(
                {
                    "severity": "critical",
                    "type": "deployment",
                    "message": f"{deployment['deployment_id']} is {deployment['status']}",
                }
            )
    return alerts


def disaster_recovery_plan() -> dict[str, Any]:
    return {
        "backup_strategy": "SQLite and config backups under vendor/backups",
        "restore_steps": [
            "restore latest config.json and iotron_state.db from backup",
            "restart FastAPI workers and background job supervisor",
            "verify device heartbeats and deployment status",
        ],
        "rpo": "depends on backup frequency",
        "rto": "minutes for local restore, longer for hardware fleet reconciliation",
    }


def _future_status(future: Future[Any]) -> dict[str, Any]:
    if future.running():
        return {"status": "running"}
    if not future.done():
        return {"status": "queued"}
    try:
        result = future.result()
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "error": str(exc)}
    return {"status": "completed", "result": result}
