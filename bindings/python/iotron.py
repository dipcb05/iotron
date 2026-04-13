"""Python-native binding helpers for IoTron."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any

from iotron import IoTronService


class NativeIoTronBridge:
    def __init__(self, library_path: str | None = None) -> None:
        env_path = library_path or os.getenv("IOTRON_NATIVE_LIB")
        self._library = ctypes.CDLL(env_path) if env_path else None
        if self._library is not None:
            self._library.iotron_manifest_json.restype = ctypes.c_void_p
            self._library.iotron_runtime_summary_json.restype = ctypes.c_void_p
            self._library.iotron_sqlite_schema.restype = ctypes.c_void_p
            self._library.iotron_free_string.argtypes = [ctypes.c_void_p]

    @property
    def available(self) -> bool:
        return self._library is not None

    def manifest_json(self) -> str:
        if self._library is None:
            raise RuntimeError("Native IoTron library is not configured. Set IOTRON_NATIVE_LIB to the compiled shared library path.")
        pointer = self._library.iotron_manifest_json()
        try:
            return ctypes.string_at(pointer).decode("utf-8")
        finally:
            self._library.iotron_free_string(pointer)

    def runtime_summary_json(self) -> str:
        if self._library is None:
            raise RuntimeError("Native IoTron library is not configured. Set IOTRON_NATIVE_LIB to the compiled shared library path.")
        pointer = self._library.iotron_runtime_summary_json()
        try:
            return ctypes.string_at(pointer).decode("utf-8")
        finally:
            self._library.iotron_free_string(pointer)

    def sqlite_schema(self) -> str:
        if self._library is None:
            raise RuntimeError("Native IoTron library is not configured. Set IOTRON_NATIVE_LIB to the compiled shared library path.")
        pointer = self._library.iotron_sqlite_schema()
        try:
            return ctypes.string_at(pointer).decode("utf-8")
        finally:
            self._library.iotron_free_string(pointer)


def default_service() -> IoTronService:
    return IoTronService()


def native_library_candidates() -> list[Path]:
    candidates = []
    for relative in ("build/iotron_native.dll", "build/libiotron_native.so", "build/libiotron_native.dylib"):
        path = Path(relative)
        if path.exists():
            candidates.append(path)
    return candidates


__all__ = ["IoTronService", "NativeIoTronBridge", "default_service", "native_library_candidates"]
