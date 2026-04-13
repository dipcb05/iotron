"""Board toolchain integration helpers for flashing and OTA flows."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .catalog import list_boards


@dataclass(frozen=True)
class ToolchainSpec:
    name: str
    executable_candidates: tuple[str, ...]
    board_prefixes: tuple[str, ...]
    summary: str


TOOLCHAINS = (
    ToolchainSpec(
        name="arduino-cli",
        executable_candidates=("arduino-cli",),
        board_prefixes=("uno", "nano", "mega", "due", "mkr1000", "arduino-"),
        summary="Compile and upload Arduino sketches through arduino-cli.",
    ),
    ToolchainSpec(
        name="esptool",
        executable_candidates=("esptool.py", "esptool"),
        board_prefixes=("esp8266", "esp32", "esp32c3", "esp32s2", "esp32s3"),
        summary="Flash ESP32 and ESP8266 firmware images using esptool.",
    ),
    ToolchainSpec(
        name="teensy-loader",
        executable_candidates=("teensy_loader_cli",),
        board_prefixes=("teensy-lc", "teensy3", "teensy4", "teensy-"),
        summary="Upload Teensy firmware through teensy_loader_cli.",
    ),
    ToolchainSpec(
        name="stm32-programmer",
        executable_candidates=("STM32_Programmer_CLI",),
        board_prefixes=("stm32",),
        summary="Program STM32 boards using STM32CubeProgrammer CLI.",
    ),
    ToolchainSpec(
        name="edge-ssh",
        executable_candidates=("scp", "ssh"),
        board_prefixes=("jetson", "raspberry-pi", "beaglebone"),
        summary="Deploy binaries and services to Linux edge boards over SSH.",
    ),
)


def supported_boards() -> list[str]:
    return sorted({item["name"] for item in list_boards()} | {f"{item['family']}-{item['name']}" for item in list_boards()})


def list_toolchains() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "available": bool(resolve_executable(spec.executable_candidates)),
            "executables": list(spec.executable_candidates),
            "boards": list(spec.board_prefixes),
            "summary": spec.summary,
        }
        for spec in TOOLCHAINS
    ]


def resolve_toolchain(board: str) -> ToolchainSpec:
    normalized = board.lower()
    for spec in TOOLCHAINS:
        if any(normalized.startswith(prefix) for prefix in spec.board_prefixes):
            return spec
    raise ValueError(f"No toolchain registered for board '{board}'")


def build_flash_plan(
    board: str,
    artifact: str,
    port: str | None = None,
    fqbn: str | None = None,
    rollout: dict[str, Any] | None = None,
    rollback_artifact: str | None = None,
) -> dict[str, Any]:
    spec = resolve_toolchain(board)
    executable = resolve_executable(spec.executable_candidates)
    artifact_path = Path(artifact)
    validation = validate_artifact(artifact_path)

    if spec.name == "arduino-cli":
        effective_fqbn = fqbn or infer_fqbn(board)
        command = [executable or spec.executable_candidates[0], "upload", "--input-dir", str(artifact_path), "--fqbn", effective_fqbn]
        if port:
            command.extend(["--port", port])
    elif spec.name == "esptool":
        chip = infer_chip(board)
        command = [
            executable or spec.executable_candidates[0],
            "--chip",
            chip,
            "--port",
            port or "/dev/ttyUSB0",
            "write_flash",
            "0x1000",
            str(artifact_path),
        ]
    elif spec.name == "teensy-loader":
        command = [executable or spec.executable_candidates[0], "--mcu", infer_teensy_mcu(board), "-w", str(artifact_path)]
    elif spec.name == "stm32-programmer":
        command = [
            executable or spec.executable_candidates[0],
            "-c",
            f"port={port or 'SWD'}",
            "-d",
            str(artifact_path),
            "0x08000000",
            "-v",
        ]
    else:
        host = port or "iot-edge.local"
        command = [executable or spec.executable_candidates[0], str(artifact_path), f"iotron@{host}:/opt/iotron/firmware/"]

    deployment_id = f"dep-{uuid4().hex[:12]}"
    rollout_policy = rollout or default_rollout_policy()
    manifest = build_artifact_manifest(artifact_path)
    return {
        "deployment_id": deployment_id,
        "operation": "flash",
        "board": board,
        "toolchain": spec.name,
        "available": bool(executable),
        "artifact": str(artifact_path),
        "artifact_sha256": validation["sha256"],
        "artifact_size": validation["size_bytes"],
        "artifact_manifest": manifest,
        "command": command,
        "rollout": rollout_policy,
        "rollback_artifact": rollback_artifact,
        "health_check": default_health_check(board),
        "notes": _notes_for_toolchain(spec.name),
        "status": "planned",
        "stage": "preflight",
    }


def build_ota_plan(
    board: str,
    artifact: str,
    host: str,
    username: str = "iotron",
    destination: str = "/opt/iotron/ota",
    rollout: dict[str, Any] | None = None,
    rollback_artifact: str | None = None,
) -> dict[str, Any]:
    spec = resolve_toolchain(board)
    executable = resolve_executable(("scp",))
    artifact_path = Path(artifact)
    validation = validate_artifact(artifact_path)
    deployment_id = f"dep-{uuid4().hex[:12]}"
    command = [executable or "scp", str(artifact_path), f"{username}@{host}:{destination}/"]
    rollout_bundle = build_ota_rollout_bundle(
        board=board,
        artifact=artifact_path,
        host=host,
        destination=destination,
        rollout=rollout or default_rollout_policy(),
        rollback_artifact=rollback_artifact,
    )
    return {
        "deployment_id": deployment_id,
        "operation": "ota",
        "board": board,
        "toolchain": spec.name,
        "available": bool(executable),
        "artifact": str(artifact_path),
        "artifact_sha256": validation["sha256"],
        "artifact_size": validation["size_bytes"],
        "artifact_manifest": build_artifact_manifest(artifact_path),
        "rollout_bundle": rollout_bundle,
        "host": host,
        "command": command,
        "rollout": rollout or default_rollout_policy(),
        "rollback_artifact": rollback_artifact,
        "health_check": default_health_check(board, host=host),
        "notes": [
            "OTA assumes an SSH-accessible edge agent or updater is already installed on the target.",
            "Use signed firmware artifacts for production rollouts.",
        ],
        "status": "planned",
        "stage": "preflight",
    }


def execute_plan(plan: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    if not plan["available"]:
        plan["executed"] = False
        plan["returncode"] = None
        plan["stdout"] = ""
        plan["stderr"] = "Required toolchain executable was not found on PATH."
        plan["status"] = "blocked"
        return plan

    artifact_check = validate_artifact(Path(plan["artifact"]), expected_sha256=plan["artifact_sha256"])
    plan["artifact_verified"] = artifact_check["verified"]
    if not artifact_check["verified"]:
        plan["executed"] = False
        plan["returncode"] = None
        plan["stdout"] = ""
        plan["stderr"] = "Artifact checksum mismatch."
        plan["status"] = "failed_preflight"
        return plan
    if plan["operation"] == "ota":
        verification = verify_ota_rollout_bundle(plan.get("rollout_bundle", {}))
        plan["rollout_verified"] = verification["verified"]
        if not verification["verified"]:
            plan["executed"] = False
            plan["returncode"] = None
            plan["stdout"] = ""
            plan["stderr"] = verification["reason"]
            plan["status"] = "failed_preflight"
            return plan

    completed = subprocess.run(plan["command"], capture_output=True, text=True, timeout=timeout, check=False)
    plan["executed"] = True
    plan["returncode"] = completed.returncode
    plan["stdout"] = completed.stdout
    plan["stderr"] = completed.stderr
    plan["stage"] = "verification"
    plan["status"] = "succeeded" if completed.returncode == 0 else "failed"
    return plan


def resolve_executable(candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def validate_artifact(path: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ValueError(f"Artifact '{path}' does not exist or is not a file")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": digest,
        "verified": expected_sha256 is None or hmac.compare_digest(digest, expected_sha256),
    }


def build_artifact_manifest(path: Path) -> dict[str, Any]:
    validation = validate_artifact(path)
    signature = sign_artifact_digest(validation["sha256"])
    return {
        "artifact": validation["path"],
        "size_bytes": validation["size_bytes"],
        "sha256": validation["sha256"],
        "signature": signature,
        "signature_algorithm": "hmac-sha256",
    }


def verify_artifact_manifest(manifest: dict[str, Any]) -> bool:
    expected = sign_artifact_digest(manifest["sha256"])
    return hmac.compare_digest(expected, manifest["signature"])


def build_ota_rollout_bundle(
    *,
    board: str,
    artifact: Path,
    host: str,
    destination: str,
    rollout: dict[str, Any],
    rollback_artifact: str | None,
) -> dict[str, Any]:
    manifest = build_artifact_manifest(artifact)
    payload = {
        "board": board,
        "artifact": manifest["artifact"],
        "artifact_sha256": manifest["sha256"],
        "host": host,
        "destination": destination,
        "rollout": rollout,
        "rollback_artifact": rollback_artifact,
        "channel": rollout.get("channel", "stable"),
    }
    signed_body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = sign_artifact_digest(hashlib.sha256(signed_body.encode("utf-8")).hexdigest())
    return {
        "payload": payload,
        "manifest": manifest,
        "signature": signature,
        "signature_algorithm": "hmac-sha256",
    }


def verify_ota_rollout_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not bundle or "payload" not in bundle or "manifest" not in bundle:
        return {"verified": False, "reason": "Missing OTA rollout bundle"}
    if not verify_artifact_manifest(bundle["manifest"]):
        return {"verified": False, "reason": "Artifact manifest signature mismatch"}
    signed_body = json.dumps(bundle["payload"], sort_keys=True, separators=(",", ":"))
    expected = sign_artifact_digest(hashlib.sha256(signed_body.encode("utf-8")).hexdigest())
    if not hmac.compare_digest(expected, bundle.get("signature", "")):
        return {"verified": False, "reason": "OTA rollout signature mismatch"}
    if bundle["payload"].get("artifact_sha256") != bundle["manifest"].get("sha256"):
        return {"verified": False, "reason": "OTA payload digest mismatch"}
    return {"verified": True, "reason": "ok"}


def sign_artifact_digest(digest: str) -> str:
    secret = os.getenv("IOTRON_ARTIFACT_SIGNING_KEY", "iotron-artifact-signing-key")
    return hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()


def default_rollout_policy() -> dict[str, Any]:
    return {
        "strategy": "staged",
        "batch_percentages": [10, 25, 50, 100],
        "require_health_confirmation": True,
        "rollback_on_failure": True,
        "retry_limit": 3,
    }


def default_health_check(board: str, host: str | None = None) -> dict[str, Any]:
    if board.startswith(("jetson", "raspberry-pi", "beaglebone")):
        return {
            "type": "ssh-service",
            "host": host or "iot-edge.local",
            "command": "systemctl is-active iotron-agent",
        }
    return {
        "type": "heartbeat",
        "expectation": "device reports heartbeat within 120 seconds after deployment",
    }


def confirm_device_health(device_id: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "status": status,
        "confirmed": status == "healthy",
        "details": details or {},
    }


def infer_fqbn(board: str) -> str:
    mapping = {
        "uno": "arduino:avr:uno",
        "nano": "arduino:avr:nano",
        "mega": "arduino:avr:mega",
        "due": "arduino:sam:arduino_due_x",
        "mkr1000": "arduino:samd:mkr1000",
    }
    normalized = board.replace("arduino-", "")
    return mapping.get(normalized, "arduino:avr:uno")


def infer_chip(board: str) -> str:
    normalized = board.lower()
    if normalized.startswith("esp8266"):
        return "esp8266"
    if normalized.startswith("esp32c3"):
        return "esp32c3"
    return "esp32"


def infer_teensy_mcu(board: str) -> str:
    normalized = board.lower()
    if "teensy4" in normalized:
        return "TEENSY40"
    if "teensy3" in normalized:
        return "mk20dx256"
    return "mkl26z64"


def _notes_for_toolchain(name: str) -> list[str]:
    notes = {
        "arduino-cli": [
            "The artifact should be an Arduino build output directory.",
            "Use a connected serial port for upload execution.",
        ],
        "esptool": [
            "The artifact should be a firmware binary produced by PlatformIO, ESP-IDF, or Arduino build tooling.",
            "Boot mode and serial permissions must be configured before execution.",
        ],
        "teensy-loader": [
            "Teensy boards require a compiled HEX artifact and access to the bootloader.",
        ],
        "stm32-programmer": [
            "STM32 flashing assumes SWD or UART access and STM32CubeProgrammer CLI installed.",
        ],
        "edge-ssh": [
            "Linux edge boards are deployed over SSH rather than raw microcontroller flashing.",
        ],
    }
    return notes.get(name, [])
