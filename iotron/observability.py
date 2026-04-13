"""Observability helpers for IoTron."""

from __future__ import annotations

import json
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


_METRICS_LOCK = threading.RLock()
_METRICS: dict[str, float] = defaultdict(float)
_LOGS: deque[dict[str, Any]] = deque(maxlen=1000)


def record_metric(name: str, value: float = 1.0) -> None:
    with _METRICS_LOCK:
        _METRICS[name] += value


def set_metric(name: str, value: float) -> None:
    with _METRICS_LOCK:
        _METRICS[name] = value


def get_metrics() -> dict[str, float]:
    with _METRICS_LOCK:
        return dict(_METRICS)


def log_event(level: str, event: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "fields": fields,
    }
    with _METRICS_LOCK:
        _LOGS.append(payload)
    return payload


def get_logs(limit: int = 100) -> list[dict[str, Any]]:
    with _METRICS_LOCK:
        return list(_LOGS)[-limit:]


def metrics_as_prometheus() -> str:
    metrics = get_metrics()
    lines = []
    for key in sorted(metrics):
        metric_name = key.replace(".", "_").replace("-", "_")
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {metrics[key]}")
    return "\n".join(lines) + ("\n" if lines else "")


def logs_as_json(limit: int = 100) -> str:
    return json.dumps(get_logs(limit=limit), indent=2)
