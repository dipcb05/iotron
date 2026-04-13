"""Build the native IoTron shared library with an available local compiler."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"

SOURCES = [
    "core/core.cpp",
    "core/c_api.cpp",
    "core/runtime_io.cpp",
    "core/storage/sqlite_handler.cpp",
    "core/protocols/i2c.cpp",
    "core/protocols/spi.cpp",
    "core/protocols/uart.cpp",
    "core/protocols/can.cpp",
    "core/protocols/modbus.cpp",
    "core/networking/mqtt.cpp",
    "core/networking/http.cpp",
    "core/networking/websocket.cpp",
    "core/networking/coap.cpp",
    "core/networking/grpc.cpp",
    "core/devices/arduino/uno.cpp",
    "core/devices/arduino/nano.cpp",
    "core/devices/arduino/mega.cpp",
    "core/devices/arduino/due.cpp",
    "core/devices/arduino/mkr1000.cpp",
    "core/devices/espressif/esp8266.cpp",
    "core/devices/espressif/esp32.cpp",
    "core/devices/espressif/esp32c3.cpp",
    "core/devices/espressif/esp32s2.cpp",
    "core/devices/espressif/esp32s3.cpp",
    "core/devices/jetson/nano.cpp",
    "core/devices/jetson/tx2.cpp",
    "core/devices/jetson/orin.cpp",
    "core/devices/jetson/agx_xavier.cpp",
    "core/devices/teensy/teensy_lc.cpp",
    "core/devices/teensy/teensy3.cpp",
    "core/devices/teensy/teensy4.cpp",
    "core/devices/stm32/stm32.cpp",
    "core/devices/raspberrypi/pi3.cpp",
    "core/devices/beaglebone/beaglebone.cpp",
]


def detect_compiler() -> tuple[str | None, list[str]]:
    for compiler in ("g++", "clang++"):
        resolved = shutil.which(compiler)
        if resolved:
            return resolved, ["-std=c++17", "-shared", "-fPIC", "-Icore", "-o"]
    resolved = shutil.which("cl")
    if resolved:
        return resolved, ["/std:c++17", "/LD", "/Icore", "/Fe:"]
    return None, []


def output_name(compiler: str) -> Path:
    if compiler.endswith("cl.exe") or compiler.lower().endswith("\\cl"):
        return BUILD_DIR / "iotron_native.dll"
    if sys.platform == "darwin":
        return BUILD_DIR / "libiotron_native.dylib"
    if sys.platform.startswith("win"):
        return BUILD_DIR / "iotron_native.dll"
    return BUILD_DIR / "libiotron_native.so"


def main() -> int:
    compiler, args = detect_compiler()
    if compiler is None:
        print("No supported C++ compiler found. Install g++, clang++, or MSVC cl.")
        return 1

    BUILD_DIR.mkdir(exist_ok=True)
    output = output_name(compiler)
    source_paths = [str(ROOT / source) for source in SOURCES]

    if compiler.endswith("cl.exe") or compiler.lower().endswith("\\cl"):
        command = [compiler, *source_paths, args[0], args[1], args[2], args[3] + str(output)]
    else:
        command = [compiler, *source_paths, *args, str(output)]

    print("Running:", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
