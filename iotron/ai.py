"""Heuristic AI planner for IoTron project setup."""

from __future__ import annotations

from typing import Any


def build_project_plan(
    goal: str,
    board: str | None = None,
    protocols: list[str] | None = None,
    networks: list[str] | None = None,
) -> dict[str, Any]:
    normalized_goal = goal.lower()
    recommended_board = board or _recommend_board(normalized_goal)
    recommended_protocols = sorted(set((protocols or []) + _recommend_protocols(normalized_goal)))
    recommended_networks = sorted(set((networks or []) + _recommend_networks(normalized_goal)))

    packages = [
        "device-registry",
        "telemetry-pipeline",
        "fastapi-gateway",
    ]
    if "dashboard" in normalized_goal or "monitor" in normalized_goal:
        packages.append("web-dashboard")
    if "ai" in normalized_goal or "anomaly" in normalized_goal or "predict" in normalized_goal:
        packages.append("ai-assistant")
    if "mqtt" in recommended_networks:
        packages.append("mqtt-broker")
    if "websocket" in recommended_networks:
        packages.append("realtime-stream")

    notes = [
        f"Recommended board: {recommended_board}",
        f"Recommended protocols: {', '.join(recommended_protocols) if recommended_protocols else 'none'}",
        f"Recommended networks: {', '.join(recommended_networks) if recommended_networks else 'none'}",
        "Use FastAPI as the control plane for APIs, orchestration, and dashboard backing services.",
    ]
    if recommended_board.startswith("jetson"):
        notes.append("Jetson-class boards are better suited for local inference, camera processing, and edge AI workloads.")
    if recommended_board.startswith("esp"):
        notes.append("ESP-class boards are a good fit for low-power telemetry, remote sensors, and OTA-managed devices.")

    return {
        "goal": goal,
        "recommended_board": recommended_board,
        "recommended_protocols": recommended_protocols,
        "recommended_networks": recommended_networks,
        "packages_to_install": sorted(set(packages)),
        "dashboard_widgets": _dashboard_widgets(normalized_goal),
        "fastapi_modules": [
            "device management",
            "telemetry ingestion",
            "dashboard summary",
            "ai planning",
        ],
        "notes": notes,
    }


def _recommend_board(goal: str) -> str:
    if any(keyword in goal for keyword in ("vision", "camera", "gpu", "video", "inference")):
        return "jetson-orin"
    if any(keyword in goal for keyword in ("battery", "low power", "portable")):
        return "esp32c3"
    if any(keyword in goal for keyword in ("education", "prototype", "maker")):
        return "arduino-uno"
    return "esp32"


def _recommend_protocols(goal: str) -> list[str]:
    recommendations: list[str] = []
    if any(keyword in goal for keyword in ("sensor", "telemetry", "monitor", "dashboard")):
        recommendations.extend(["i2c", "uart"])
    if any(keyword in goal for keyword in ("industrial", "plc", "factory")):
        recommendations.extend(["modbus", "can"])
    if "display" in goal or "storage" in goal:
        recommendations.append("spi")
    return recommendations


def _recommend_networks(goal: str) -> list[str]:
    recommendations = ["http"]
    if any(keyword in goal for keyword in ("telemetry", "stream", "realtime", "dashboard", "mqtt")):
        recommendations.append("mqtt")
        recommendations.append("websocket")
    if any(keyword in goal for keyword in ("constrained", "mesh", "low bandwidth")):
        recommendations.append("coap")
    if any(keyword in goal for keyword in ("service", "edge cluster", "microservice")):
        recommendations.append("grpc")
    return recommendations


def _dashboard_widgets(goal: str) -> list[str]:
    widgets = ["device status", "protocol health", "network events"]
    if any(keyword in goal for keyword in ("telemetry", "sensor", "dashboard")):
        widgets.append("telemetry charts")
    if any(keyword in goal for keyword in ("alert", "anomaly", "predict")):
        widgets.append("ai alerts")
    if "camera" in goal or "vision" in goal:
        widgets.append("video stream")
    return widgets
