"""Application service layer for CLI and API use."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .ai import build_project_plan
from .catalog import BOARD_FAMILIES, NETWORKS, PROTOCOLS, list_boards
from .observability import get_logs, get_metrics, log_event, metrics_as_prometheus, record_metric, set_metric
from .operations import (
    create_backup,
    disaster_recovery_plan,
    generate_alerts,
    get_job,
    list_backups,
    list_jobs,
    restore_backup,
    submit_job,
)
from .security import issue_device_token, issue_operator_token
from .storage import (
    list_audit_events,
    list_deployments,
    load_config,
    load_packages,
    load_runtime_state,
    log_audit_event,
    prune_telemetry,
    save_config,
    save_deployment,
    save_packages,
    save_runtime_state,
)
from .toolchains import (
    build_flash_plan,
    build_ota_plan,
    confirm_device_health,
    execute_plan,
    list_toolchains,
)


class IoTronService:
    def __init__(self) -> None:
        self._config = load_config()
        self._packages = load_packages()
        self._runtime_state = load_runtime_state()
        set_metric("iotron.devices", len(self._runtime_state.get("devices", [])))
        set_metric("iotron.packages", len(self._packages.get("packages", [])))

    def refresh(self) -> None:
        self._config = load_config()
        self._packages = load_packages()
        self._runtime_state = load_runtime_state()

    def status(self) -> dict[str, Any]:
        return {
            "project": self._config["project"],
            "version": self._config["version"],
            "selected_board": self._config.get("selected_board"),
            "enabled_protocols": self._config.get("enabled_protocols", []),
            "enabled_networks": self._config.get("enabled_networks", []),
            "features": self._config.get("features", {}),
            "installed_packages": self._packages.get("packages", []),
            "dashboard_url": "/dashboard",
            "registered_devices": len(self._runtime_state.get("devices", [])),
        }

    def list_boards(self, family: str | None = None) -> list[dict[str, str]]:
        boards = list_boards()
        if family is None:
            return boards
        return [board for board in boards if board["family"] == family]

    def list_protocols(self) -> dict[str, dict[str, str]]:
        return PROTOCOLS

    def list_networks(self) -> dict[str, dict[str, str]]:
        return NETWORKS

    def list_toolchains(self) -> list[dict[str, Any]]:
        return list_toolchains()

    def list_packages(self) -> list[dict[str, str]]:
        return self._packages.get("packages", [])

    def list_devices(self) -> list[dict[str, Any]]:
        return self._runtime_state.get("devices", [])

    def list_telemetry(self, device_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        events = self._runtime_state.get("telemetry", [])
        if device_id is not None:
            events = [event for event in events if event["device_id"] == device_id]
        return events[-limit:]

    def list_deployments(self, limit: int = 100) -> list[dict[str, Any]]:
        return list_deployments(limit=limit)

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return list_audit_events(limit=limit)

    def get_metrics(self) -> dict[str, float]:
        return get_metrics()

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return get_logs(limit=limit)

    def metrics_export(self) -> str:
        return metrics_as_prometheus()

    def get_alerts(self) -> list[dict[str, Any]]:
        return generate_alerts(self.list_devices(), self.list_deployments(limit=100))

    def list_backups(self) -> list[dict[str, Any]]:
        return list_backups()

    def create_backup(self, actor: str = "system") -> dict[str, Any]:
        result = create_backup()
        self._log(actor, "create_backup", "backup", result["backup_id"], result)
        return result

    def restore_backup(self, backup_id: str, actor: str = "system") -> dict[str, Any]:
        result = restore_backup(backup_id)
        self.refresh()
        self._log(actor, "restore_backup", "backup", backup_id, result)
        return result

    def disaster_recovery_plan(self) -> dict[str, Any]:
        return disaster_recovery_plan()

    def submit_job(self, name: str, fn, *args, **kwargs) -> dict[str, Any]:
        return submit_job(name, fn, *args, **kwargs)

    def list_jobs(self) -> list[dict[str, Any]]:
        return list_jobs()

    def get_job(self, job_id: str) -> dict[str, Any]:
        return get_job(job_id)

    def install_package(self, name: str, version: str = "latest", actor: str = "system") -> dict[str, str]:
        existing = self._find_package(name)
        package_record = {
            "name": name,
            "version": version,
            "installed_at": self._timestamp(),
            "status": "installed",
        }
        if existing is None:
            self._packages["packages"].append(package_record)
        else:
            existing.update(package_record)
        self._save_packages()
        self._log(actor, "install_package", "package", name, package_record)
        record_metric("packages.installed", 1)
        return package_record

    def uninstall_package(self, name: str, actor: str = "system") -> bool:
        packages = self._packages.get("packages", [])
        before = len(packages)
        self._packages["packages"] = [item for item in packages if item["name"] != name]
        changed = len(self._packages["packages"]) != before
        if changed:
            self._save_packages()
            self._log(actor, "uninstall_package", "package", name, {})
            record_metric("packages.uninstalled", 1)
        return changed

    def update_package(self, name: str, version: str = "latest", actor: str = "system") -> dict[str, str]:
        existing = self._find_package(name)
        package_record = {
            "name": name,
            "version": version,
            "installed_at": self._timestamp(),
            "status": "updated",
        }
        if existing is None:
            self._packages["packages"].append(package_record)
        else:
            existing.update(package_record)
        self._save_packages()
        self._log(actor, "update_package", "package", name, package_record)
        record_metric("packages.updated", 1)
        return package_record

    def select_board(self, board: str, actor: str = "system") -> dict[str, Any]:
        supported = {entry["name"] for entry in list_boards()}
        supported |= {f"{family}-{name}" for family, names in BOARD_FAMILIES.items() for name in names}
        if board not in supported:
            raise ValueError(f"Unsupported board '{board}'")
        self._config["selected_board"] = board
        self._save_config()
        self._log(actor, "select_board", "project", self._config["project"], {"board": board})
        return self.status()

    def enable_protocol(self, name: str, actor: str = "system") -> dict[str, Any]:
        if name not in PROTOCOLS:
            raise ValueError(f"Unsupported protocol '{name}'")
        enabled = self._config.setdefault("enabled_protocols", [])
        if name not in enabled:
            enabled.append(name)
            enabled.sort()
            self._save_config()
            self._log(actor, "enable_protocol", "protocol", name, {})
        return self.status()

    def enable_network(self, name: str, actor: str = "system") -> dict[str, Any]:
        if name not in NETWORKS:
            raise ValueError(f"Unsupported network '{name}'")
        enabled = self._config.setdefault("enabled_networks", [])
        if name not in enabled:
            enabled.append(name)
            enabled.sort()
            self._save_config()
            self._log(actor, "enable_network", "network", name, {})
        return self.status()

    def install_web_dashboard(self, actor: str = "system") -> dict[str, Any]:
        self.install_package("web-dashboard", actor=actor)
        self.install_package("dashboard-charts", actor=actor)
        self.install_package("realtime-stream", actor=actor)
        self._config.setdefault("features", {})["web_dashboard"] = True
        if "http" not in self._config.setdefault("enabled_networks", []):
            self._config["enabled_networks"].append("http")
        if "websocket" not in self._config["enabled_networks"]:
            self._config["enabled_networks"].append("websocket")
        self._config["enabled_networks"].sort()
        self._save_config()
        self._log(actor, "install_dashboard", "feature", "web_dashboard", {})
        return self.status()

    def dashboard_summary(self) -> dict[str, Any]:
        status = self.status()
        return {
            "project": status["project"],
            "selected_board": status["selected_board"],
            "package_count": len(status["installed_packages"]),
            "protocol_count": len(status["enabled_protocols"]),
            "network_count": len(status["enabled_networks"]),
            "dashboard_enabled": status["features"].get("web_dashboard", False),
            "toolchain_count": len(self.list_toolchains()),
            "device_count": len(self._runtime_state.get("devices", [])),
        }

    def dashboard_data(self) -> dict[str, Any]:
        return {
            "summary": self.dashboard_summary(),
            "status": self.status(),
            "boards": self.list_boards(),
            "protocols": self.list_protocols(),
            "networks": self.list_networks(),
            "toolchains": self.list_toolchains(),
            "packages": self.list_packages(),
            "devices": self.list_devices(),
            "telemetry": self.list_telemetry(limit=25),
            "deployments": self.list_deployments(limit=10),
            "audit_log": self.list_audit_events(limit=10),
        }

    def register_device(
        self,
        device_id: str,
        board: str,
        protocol: str | None = None,
        network: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        supported = {entry["name"] for entry in list_boards()}
        supported |= {f"{family}-{name}" for family, names in BOARD_FAMILIES.items() for name in names}
        if board not in supported:
            raise ValueError(f"Unsupported board '{board}'")
        if protocol and protocol not in PROTOCOLS:
            raise ValueError(f"Unsupported protocol '{protocol}'")
        if network and network not in NETWORKS:
            raise ValueError(f"Unsupported network '{network}'")

        device_token = issue_device_token(device_id)
        device = self._find_device(device_id)
        payload = {
            "device_id": device_id,
            "board": board,
            "protocol": protocol,
            "network": network,
            "metadata": metadata or {},
            "registered_at": self._timestamp(),
            "last_seen": self._timestamp(),
            "auth_identity": f"device:{device_id}",
        }
        if device is None:
            self._runtime_state.setdefault("devices", []).append(payload)
        else:
            device.update(payload)
        self._save_runtime_state()
        self._log(actor, "register_device", "device", device_id, payload)
        record_metric("devices.registered", 1)
        payload["device_token"] = device_token
        return payload

    def heartbeat_device(self, device_id: str, actor: str = "device") -> dict[str, Any]:
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Unknown device '{device_id}'")
        device["last_seen"] = self._timestamp()
        self._save_runtime_state()
        self._log(actor, "heartbeat_device", "device", device_id, {"last_seen": device["last_seen"]})
        record_metric("devices.heartbeat", 1)
        return device

    def ingest_telemetry(
        self,
        device_id: str,
        metric: str,
        value: Any,
        recorded_at: str | None = None,
        actor: str = "device",
    ) -> dict[str, Any]:
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Unknown device '{device_id}'")
        event = {
            "device_id": device_id,
            "metric": metric,
            "value": value,
            "recorded_at": recorded_at or self._timestamp(),
        }
        self._runtime_state.setdefault("telemetry", []).append(event)
        device["last_seen"] = event["recorded_at"]
        self._save_runtime_state()
        self._log(actor, "ingest_telemetry", "device", device_id, {"metric": metric})
        record_metric("telemetry.ingested", 1)
        return event

    def confirm_device_deployment(self, device_id: str, status: str, details: dict[str, Any] | None = None, actor: str = "device") -> dict[str, Any]:
        result = confirm_device_health(device_id, status, details)
        self._log(actor, "confirm_device_deployment", "device", device_id, result)
        record_metric("deployments.health_confirmation", 1)
        return result

    def flash_firmware(
        self,
        board: str,
        artifact: str,
        port: str | None = None,
        fqbn: str | None = None,
        execute: bool = False,
        rollout: dict[str, Any] | None = None,
        rollback_artifact: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        plan = build_flash_plan(
            board=board,
            artifact=artifact,
            port=port,
            fqbn=fqbn,
            rollout=rollout,
            rollback_artifact=rollback_artifact,
        )
        if execute:
            plan = execute_plan(plan)
        self._record_deployment(plan, actor=actor)
        record_metric("deployments.flash", 1)
        return plan

    def ota_update(
        self,
        board: str,
        artifact: str,
        host: str,
        username: str = "iotron",
        destination: str = "/opt/iotron/ota",
        execute: bool = False,
        rollout: dict[str, Any] | None = None,
        rollback_artifact: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        plan = build_ota_plan(
            board=board,
            artifact=artifact,
            host=host,
            username=username,
            destination=destination,
            rollout=rollout,
            rollback_artifact=rollback_artifact,
        )
        if execute:
            plan = execute_plan(plan)
        self._record_deployment(plan, actor=actor)
        record_metric("deployments.ota", 1)
        return plan

    def issue_operator_token(self, subject: str, role: str = "admin", actor: str = "system") -> dict[str, str]:
        token = issue_operator_token(subject, role=role)
        self._log(actor, "issue_operator_token", "identity", subject, {"role": role})
        return {"subject": subject, "role": role, "token": token}

    def backend_overview(self) -> dict[str, Any]:
        return {
            "service": {
                "name": self._config["project"],
                "version": self._config["version"],
                "features": self._config.get("features", {}),
            },
            "inventory": {
                "devices": len(self._runtime_state.get("devices", [])),
                "packages": len(self._packages.get("packages", [])),
                "protocols": len(PROTOCOLS),
                "networks": len(NETWORKS),
                "deployments": len(self.list_deployments(limit=1000)),
            },
            "ingestion": {
                "telemetry_events": len(self._runtime_state.get("telemetry", [])),
                "recent_events": self.list_telemetry(limit=10),
                "retention_action": "SQLite-backed event log with pruning support",
            },
            "security": {
                "auth_modes": ["api_key", "bearer_operator", "bearer_device"],
                "audit_events": len(self.list_audit_events(limit=1000)),
            },
        }

    def runtime_manifest(self) -> dict[str, Any]:
        return {
            "devices": self.list_boards(),
            "protocols": self.list_protocols(),
            "networks": self.list_networks(),
            "storage": {
                "name": "sqlite-local",
                "driver": "sqlite3",
                "path": "vendor/iotron_state.db",
                "retention_policy": "latest 1000 telemetry events per device with audit log retention",
            },
        }

    def prune_runtime_data(self, retain_latest_per_device: int = 1000, actor: str = "system") -> dict[str, Any]:
        deleted = prune_telemetry(retain_latest_per_device=retain_latest_per_device)
        self.refresh()
        self._log(actor, "prune_runtime_data", "telemetry", "global", {"deleted": deleted})
        record_metric("telemetry.pruned", deleted)
        return {"deleted_telemetry_events": deleted}

    def ai_plan(
        self,
        goal: str,
        board: str | None = None,
        protocols: list[str] | None = None,
        networks: list[str] | None = None,
    ) -> dict[str, Any]:
        return build_project_plan(goal, board=board, protocols=protocols, networks=networks)

    def export_config(self) -> dict[str, Any]:
        return self._config

    def _record_deployment(self, plan: dict[str, Any], actor: str) -> None:
        timestamp = self._timestamp()
        record = {
            "deployment_id": plan["deployment_id"],
            "operation": plan["operation"],
            "board": plan["board"],
            "artifact": plan["artifact"],
            "artifact_sha256": plan["artifact_sha256"],
            "stage": plan.get("stage", "planned"),
            "status": plan.get("status", "planned"),
            "rollout": plan.get("rollout", {}),
            "rollback_artifact": plan.get("rollback_artifact"),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        save_deployment(record)
        self._log(actor, f"{plan['operation']}_deployment", "deployment", plan["deployment_id"], record)
        log_event("info", "deployment_recorded", deployment_id=plan["deployment_id"], status=plan.get("status", "planned"))

    def _find_package(self, name: str) -> dict[str, str] | None:
        for package in self._packages.get("packages", []):
            if package["name"] == name:
                return package
        return None

    def _find_device(self, device_id: str) -> dict[str, Any] | None:
        for device in self._runtime_state.get("devices", []):
            if device["device_id"] == device_id:
                return device
        return None

    def _save_config(self) -> None:
        save_config(self._config)
        self.refresh()

    def _save_packages(self) -> None:
        save_packages(self._packages)
        self.refresh()

    def _save_runtime_state(self) -> None:
        save_runtime_state(self._runtime_state)
        self.refresh()

    def _log(self, actor: str, action: str, resource_type: str, resource_id: str, metadata: dict[str, Any]) -> None:
        log_audit_event(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            created_at=self._timestamp(),
        )
        log_event("info", action, actor=actor, resource_type=resource_type, resource_id=resource_id)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
