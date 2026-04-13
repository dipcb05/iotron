"""Hardware validation helpers for board lab execution and preflight checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .toolchains import (
    build_flash_plan,
    build_ota_plan,
    confirm_device_health,
    resolve_executable,
    verify_artifact_manifest,
)


def run_hardware_validation(
    board: str,
    artifact: str,
    port: str | None = None,
    fqbn: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    artifact_path = Path(artifact)
    if host:
        plan = build_ota_plan(board=board, artifact=artifact, host=host)
        validation_type = "ota"
    else:
        plan = build_flash_plan(board=board, artifact=artifact, port=port, fqbn=fqbn)
        validation_type = "flash"

    required_executables = _extract_executables(plan["command"])
    available_executables = {
        executable: bool(resolve_executable((executable,)))
        for executable in required_executables
    }
    manifest_valid = verify_artifact_manifest(plan["artifact_manifest"])
    health_probe = confirm_device_health(
        device_id=f"lab-{board}",
        status="healthy" if plan["available"] and manifest_valid else "blocked",
        details={"validation_type": validation_type},
    )
    blocked_reasons = []
    if not artifact_path.exists():
        blocked_reasons.append("artifact_missing")
    if not manifest_valid:
        blocked_reasons.append("artifact_manifest_invalid")
    if not all(available_executables.values()):
        blocked_reasons.append("toolchain_missing")
    if validation_type == "flash" and not port and board.startswith(("esp", "uno", "nano", "mega", "stm32", "teensy")):
        blocked_reasons.append("port_not_provided")
    if validation_type == "ota" and not host:
        blocked_reasons.append("host_not_provided")

    return {
        "board": board,
        "artifact": str(artifact_path),
        "validation_type": validation_type,
        "plan": plan,
        "manifest_verified": manifest_valid,
        "executables": available_executables,
        "health_probe": health_probe,
        "lab_ready": not blocked_reasons,
        "status": "ready" if not blocked_reasons else "blocked",
        "blocked_reasons": blocked_reasons,
        "runbook": _validation_runbook(validation_type),
    }


def _extract_executables(command: list[str]) -> list[str]:
    if not command:
        return []
    return sorted({Path(command[0]).name})


def _validation_runbook(validation_type: str) -> list[str]:
    common = [
        "Verify the artifact digest and signature before deployment.",
        "Record serial number, board revision, and current firmware version.",
        "Capture logs and heartbeat timing after deployment.",
    ]
    if validation_type == "ota":
        return common + [
            "Confirm the updater service is reachable over SSH.",
            "Validate rollback artifact availability before rollout.",
            "Confirm the device reports healthy status after service restart.",
        ]
    return common + [
        "Connect the target port and place the device in programming mode if required.",
        "Run the flashing command on a dedicated lab host with the vendor CLI installed.",
        "Confirm the device reboots and publishes a post-flash heartbeat.",
    ]
