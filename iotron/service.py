"""Application service layer for CLI and API use."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .ai import build_project_plan
from .catalog import BOARD_FAMILIES, NETWORKS, PROTOCOLS, list_boards
from .storage import (
    load_config,
    load_packages,
    load_runtime_state,
    save_config,
    save_packages,
    save_runtime_state,
)
from .toolchains import build_flash_plan, build_ota_plan, execute_plan, list_toolchains


class IoTronService:
    def __init__(self) -> None:
        self._config = load_config()
        self._packages = load_packages()
        self._runtime_state = load_runtime_state()

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

    def install_package(self, name: str, version: str = "latest") -> dict[str, str]:
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
        return package_record

    def uninstall_package(self, name: str) -> bool:
        packages = self._packages.get("packages", [])
        before = len(packages)
        self._packages["packages"] = [item for item in packages if item["name"] != name]
        changed = len(self._packages["packages"]) != before
        if changed:
            self._save_packages()
        return changed

    def update_package(self, name: str, version: str = "latest") -> dict[str, str]:
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
        return package_record

    def select_board(self, board: str) -> dict[str, Any]:
        supported = {entry["name"] for entry in list_boards()}
        supported |= {f"{family}-{name}" for family, names in BOARD_FAMILIES.items() for name in names}
        if board not in supported:
            raise ValueError(f"Unsupported board '{board}'")
        self._config["selected_board"] = board
        self._save_config()
        return self.status()

    def enable_protocol(self, name: str) -> dict[str, Any]:
        if name not in PROTOCOLS:
            raise ValueError(f"Unsupported protocol '{name}'")
        enabled = self._config.setdefault("enabled_protocols", [])
        if name not in enabled:
            enabled.append(name)
            enabled.sort()
            self._save_config()
        return self.status()

    def enable_network(self, name: str) -> dict[str, Any]:
        if name not in NETWORKS:
            raise ValueError(f"Unsupported network '{name}'")
        enabled = self._config.setdefault("enabled_networks", [])
        if name not in enabled:
            enabled.append(name)
            enabled.sort()
            self._save_config()
        return self.status()

    def install_web_dashboard(self) -> dict[str, Any]:
        self.install_package("web-dashboard")
        self.install_package("dashboard-charts")
        self.install_package("realtime-stream")
        self._config.setdefault("features", {})["web_dashboard"] = True
        if "http" not in self._config.setdefault("enabled_networks", []):
            self._config["enabled_networks"].append("http")
        if "websocket" not in self._config["enabled_networks"]:
            self._config["enabled_networks"].append("websocket")
        self._config["enabled_networks"].sort()
        self._save_config()
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
        }

    def list_devices(self) -> list[dict[str, Any]]:
        return self._runtime_state.get("devices", [])

    def register_device(
        self,
        device_id: str,
        board: str,
        protocol: str | None = None,
        network: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        supported = {entry["name"] for entry in list_boards()}
        supported |= {f"{family}-{name}" for family, names in BOARD_FAMILIES.items() for name in names}
        if board not in supported:
            raise ValueError(f"Unsupported board '{board}'")
        if protocol and protocol not in PROTOCOLS:
            raise ValueError(f"Unsupported protocol '{protocol}'")
        if network and network not in NETWORKS:
            raise ValueError(f"Unsupported network '{network}'")

        device = self._find_device(device_id)
        payload = {
            "device_id": device_id,
            "board": board,
            "protocol": protocol,
            "network": network,
            "metadata": metadata or {},
            "registered_at": self._timestamp(),
            "last_seen": self._timestamp(),
        }
        if device is None:
            self._runtime_state.setdefault("devices", []).append(payload)
        else:
            device.update(payload)
        self._save_runtime_state()
        return payload

    def heartbeat_device(self, device_id: str) -> dict[str, Any]:
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Unknown device '{device_id}'")
        device["last_seen"] = self._timestamp()
        self._save_runtime_state()
        return device

    def ingest_telemetry(
        self,
        device_id: str,
        metric: str,
        value: Any,
        recorded_at: str | None = None,
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
        return event

    def list_telemetry(self, device_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        events = self._runtime_state.get("telemetry", [])
        if device_id is not None:
            events = [event for event in events if event["device_id"] == device_id]
        return events[-limit:]

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
            },
            "ingestion": {
                "telemetry_events": len(self._runtime_state.get("telemetry", [])),
                "recent_events": self.list_telemetry(limit=10),
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
                "path": "vendor/iotron_runtime.db",
                "retention_policy": "30 days hot telemetry with manifest journaling",
            },
        }

    def flash_firmware(
        self,
        board: str,
        artifact: str,
        port: str | None = None,
        fqbn: str | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        plan = build_flash_plan(board=board, artifact=artifact, port=port, fqbn=fqbn)
        if execute:
            return execute_plan(plan)
        return plan

    def ota_update(
        self,
        board: str,
        artifact: str,
        host: str,
        username: str = "iotron",
        destination: str = "/opt/iotron/ota",
        execute: bool = False,
    ) -> dict[str, Any]:
        plan = build_ota_plan(
            board=board,
            artifact=artifact,
            host=host,
            username=username,
            destination=destination,
        )
        if execute:
            return execute_plan(plan)
        return plan

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

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
