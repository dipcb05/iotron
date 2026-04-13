"""Board toolchain integration helpers for flashing and OTA flows."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
) -> dict[str, Any]:
    spec = resolve_toolchain(board)
    executable = resolve_executable(spec.executable_candidates)
    artifact_path = str(Path(artifact))

    if spec.name == "arduino-cli":
        effective_fqbn = fqbn or infer_fqbn(board)
        command = [executable or spec.executable_candidates[0], "upload", "--input-dir", artifact_path, "--fqbn", effective_fqbn]
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
            artifact_path,
        ]
    elif spec.name == "teensy-loader":
        command = [executable or spec.executable_candidates[0], "--mcu", infer_teensy_mcu(board), "-w", artifact_path]
    elif spec.name == "stm32-programmer":
        command = [
            executable or spec.executable_candidates[0],
            "-c",
            f"port={port or 'SWD'}",
            "-d",
            artifact_path,
            "0x08000000",
            "-v",
        ]
    else:
        host = port or "iot-edge.local"
        command = [executable or spec.executable_candidates[0], artifact_path, f"iotron@{host}:/opt/iotron/firmware/"]

    return {
        "operation": "flash",
        "board": board,
        "toolchain": spec.name,
        "available": bool(executable),
        "artifact": artifact_path,
        "command": command,
        "notes": _notes_for_toolchain(spec.name),
    }


def build_ota_plan(
    board: str,
    artifact: str,
    host: str,
    username: str = "iotron",
    destination: str = "/opt/iotron/ota",
) -> dict[str, Any]:
    spec = resolve_toolchain(board)
    executable = resolve_executable(("scp",))
    artifact_path = str(Path(artifact))
    command = [executable or "scp", artifact_path, f"{username}@{host}:{destination}/"]
    return {
        "operation": "ota",
        "board": board,
        "toolchain": spec.name,
        "available": bool(executable),
        "artifact": artifact_path,
        "host": host,
        "command": command,
        "notes": [
            "OTA assumes an SSH-accessible edge agent or updater is already installed on the target.",
            "Use signed firmware artifacts for production rollouts.",
        ],
    }


def execute_plan(plan: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    if not plan["available"]:
        plan["executed"] = False
        plan["returncode"] = None
        plan["stdout"] = ""
        plan["stderr"] = "Required toolchain executable was not found on PATH."
        return plan

    completed = subprocess.run(plan["command"], capture_output=True, text=True, timeout=timeout, check=False)
    plan["executed"] = True
    plan["returncode"] = completed.returncode
    plan["stdout"] = completed.stdout
    plan["stderr"] = completed.stderr
    return plan


def resolve_executable(candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


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
