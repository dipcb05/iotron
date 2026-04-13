"""Operational helpers for jobs, alerts, and backup/restore."""

from __future__ import annotations

import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .observability import log_event, record_metric
from .storage import (
    CONFIG_PATH,
    SQLITE_DB_PATH,
    claim_next_job,
    get_job_record,
    list_job_records,
    list_notification_channels,
    project_root,
    save_job,
)

_EXECUTOR = ThreadPoolExecutor(max_workers=4)
_JOBS_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_LOCAL_HANDLERS: dict[str, Callable[..., Any]] = {}


def submit_job(name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    job_id = f"job-{uuid4().hex[:12]}"
    submitted_at = datetime.now(timezone.utc).isoformat()
    backend = os.getenv("IOTRON_WORKER_BACKEND", "local").strip().lower() or "local"
    record = {
        "job_id": job_id,
        "name": name,
        "backend": "sqlite" if backend in {"sqlite", "remote"} else "local",
        "status": "queued",
        "payload": {"args": list(args), "kwargs": kwargs},
        "result": None,
        "error": None,
        "submitted_at": submitted_at,
        "updated_at": submitted_at,
        "claimed_by": None,
    }
    save_job(record)
    _LOCAL_HANDLERS[job_id] = fn
    future = _EXECUTOR.submit(_execute_local_job, job_id, fn, *args, **kwargs) if backend == "local" else None
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "name": name,
            "status": "queued",
            "submitted_at": submitted_at,
            "future": future,
            "backend": record["backend"],
        }
    record_metric("jobs.submitted", 1)
    log_event("info", "job_submitted", job_id=job_id, name=name, backend=record["backend"])
    return {"job_id": job_id, "name": name, "status": "queued", "submitted_at": submitted_at, "backend": record["backend"]}


def list_jobs() -> list[dict[str, Any]]:
    jobs = {item["job_id"]: item for item in list_job_records(limit=200)}
    with _JOBS_LOCK:
        for job in _JOBS.values():
            payload = dict(job)
            future = payload.pop("future")
            if future is not None:
                payload.update(_future_status(future))
            jobs[payload["job_id"]] = {**jobs.get(payload["job_id"], {}), **payload}
    return sorted(jobs.values(), key=lambda item: item["submitted_at"], reverse=True)


def get_job(job_id: str) -> dict[str, Any]:
    durable = get_job_record(job_id)
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            if durable is None:
                raise KeyError(job_id)
            return durable
        payload = dict(job)
        future = payload.pop("future")
        if future is not None:
            payload.update(_future_status(future))
        return {**(durable or {}), **payload}


def claim_job(worker_id: str) -> dict[str, Any] | None:
    job = claim_next_job(worker_id)
    if job:
        log_event("info", "job_claimed", job_id=job["job_id"], worker_id=worker_id)
    return job


def complete_job(job_id: str, result: Any = None, error: str | None = None) -> dict[str, Any]:
    record = get_job_record(job_id)
    if record is None:
        raise KeyError(job_id)
    record["status"] = "failed" if error else "completed"
    record["result"] = result
    record["error"] = error
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_job(record)
    log_event("info" if not error else "error", "job_completed", job_id=job_id, status=record["status"])
    return record


def worker_metadata() -> dict[str, Any]:
    backend = os.getenv("IOTRON_WORKER_BACKEND", "local").strip().lower() or "local"
    return {
        "backend": backend,
        "distributed": backend in {"sqlite", "remote"},
        "queue": "sqlite.jobs" if backend in {"sqlite", "remote"} else "in_process",
        "remote_endpoint": os.getenv("IOTRON_REMOTE_WORKER_URL"),
    }


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
        "automation": {
            "pre_restore_checks": ["verify backup id", "stop API workers", "pause deployment jobs"],
            "post_restore_checks": ["restart workers", "replay alert notifications", "verify device heartbeats"],
        },
        "restore_steps": [
            "restore latest config.json and iotron_state.db from backup",
            "restart FastAPI workers and background job supervisor",
            "verify device heartbeats and deployment status",
        ],
        "rpo": "depends on backup frequency",
        "rto": "minutes for local restore, longer for hardware fleet reconciliation",
    }


def dispatch_notifications(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deliveries = []
    channels = [channel for channel in list_notification_channels() if channel.get("enabled")]
    for channel in channels:
        payload = {
            "channel_id": channel["channel_id"],
            "channel_type": channel["channel_type"],
            "target": channel["target"],
            "alert_count": len(alerts),
            "status": "dispatched",
        }
        deliveries.append(payload)
        log_event("warning", "notification_dispatched", **payload)
    if deliveries:
        record_metric("notifications.dispatched", len(deliveries))
    return deliveries


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


def _execute_local_job(job_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    record = get_job_record(job_id)
    if record:
        record["status"] = "running"
        record["claimed_by"] = "local-executor"
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_job(record)
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        complete_job(job_id, error=str(exc))
        raise
    complete_job(job_id, result=result)
    return result
