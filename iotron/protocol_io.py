"""Protocol and bus adapters for live broker and transport exchanges."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

def protocol_capabilities() -> dict[str, dict[str, Any]]:
    return {
        "http": {"available": True, "mode": "request_response"},
        "tcp": {"available": True, "mode": "stream"},
        "udp": {"available": True, "mode": "datagram"},
        "mqtt": {"available": _optional_module("paho.mqtt.publish"), "mode": "broker"},
        "websocket": {"available": _optional_module("websocket"), "mode": "broker"},
        "serial": {"available": _optional_module("serial"), "mode": "bus"},
        "i2c": {"available": _optional_module("smbus2"), "mode": "bus"},
    }


def protocol_exchange(
    protocol: str,
    target: str,
    operation: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    payload = payload or {}
    if protocol == "http":
        return _http_exchange(target, operation, payload, timeout)
    if protocol == "tcp":
        return _tcp_exchange(target, operation, payload, timeout)
    if protocol == "udp":
        return _udp_exchange(target, operation, payload, timeout)
    if protocol == "mqtt":
        return _mqtt_exchange(target, operation, payload, timeout)
    if protocol == "websocket":
        return _websocket_exchange(target, operation, payload, timeout)
    if protocol == "serial":
        return _serial_exchange(target, operation, payload, timeout)
    if protocol == "i2c":
        return _i2c_exchange(target, operation, payload, timeout)
    raise ValueError(f"Unsupported protocol '{protocol}'")


@dataclass(frozen=True)
class SocketTarget:
    host: str
    port: int


def _http_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover
        raise ValueError("HTTP protocol exchange requires 'httpx' to be installed") from exc
    method = operation.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError(f"Unsupported HTTP method '{operation}'")
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, target, json=payload if method != "GET" else None, params=payload if method == "GET" else None)
    body: Any
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return {
        "protocol": "http",
        "target": target,
        "operation": method,
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
    }


def _tcp_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    socket_target = _parse_socket_target(target)
    message = _payload_to_bytes(operation, payload)
    with socket.create_connection((socket_target.host, socket_target.port), timeout=timeout) as client:
        client.sendall(message)
        response = client.recv(int(payload.get("read_size", 4096)))
    return {
        "protocol": "tcp",
        "target": target,
        "operation": operation,
        "request_bytes": len(message),
        "response_text": response.decode("utf-8", errors="replace"),
    }


def _udp_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    socket_target = _parse_socket_target(target)
    message = _payload_to_bytes(operation, payload)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(timeout)
        client.sendto(message, (socket_target.host, socket_target.port))
        response, remote = client.recvfrom(int(payload.get("read_size", 4096)))
    return {
        "protocol": "udp",
        "target": target,
        "operation": operation,
        "remote": {"host": remote[0], "port": remote[1]},
        "response_text": response.decode("utf-8", errors="replace"),
    }


def _mqtt_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        import paho.mqtt.publish as publish
    except ImportError as exc:  # pragma: no cover
        raise ValueError("MQTT support requires 'paho-mqtt' to be installed") from exc
    parsed = urlparse(target if "://" in target else f"mqtt://{target}")
    topic = payload.get("topic")
    if not topic:
        raise ValueError("MQTT exchange requires a 'topic' field")
    publish.single(
        topic,
        payload=json.dumps(payload.get("message", {})),
        hostname=parsed.hostname or "127.0.0.1",
        port=parsed.port or 1883,
        client_id=payload.get("client_id", "iotron"),
        keepalive=int(timeout),
    )
    return {
        "protocol": "mqtt",
        "target": target,
        "operation": operation,
        "topic": topic,
        "published": True,
    }


def _websocket_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        import websocket
    except ImportError as exc:  # pragma: no cover
        raise ValueError("WebSocket support requires 'websocket-client' to be installed") from exc
    ws = websocket.create_connection(target, timeout=timeout)
    try:
        ws.send(json.dumps({"operation": operation, "payload": payload}))
        response = ws.recv()
    finally:
        ws.close()
    return {
        "protocol": "websocket",
        "target": target,
        "operation": operation,
        "response": response,
    }


def _serial_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        import serial
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Serial support requires 'pyserial' to be installed") from exc
    baudrate = int(payload.get("baudrate", 115200))
    message = _payload_to_bytes(operation, payload)
    with serial.Serial(target, baudrate=baudrate, timeout=timeout) as port:
        port.write(message)
        response = port.read(int(payload.get("read_size", 256)))
    return {
        "protocol": "serial",
        "target": target,
        "operation": operation,
        "baudrate": baudrate,
        "response_hex": response.hex(),
    }


def _i2c_exchange(target: str, operation: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    del timeout
    try:
        from smbus2 import SMBus
    except ImportError as exc:  # pragma: no cover
        raise ValueError("I2C support requires 'smbus2' to be installed") from exc
    bus_id = int(payload.get("bus", 1))
    address = int(payload.get("address", "0x40"), 0) if isinstance(payload.get("address"), str) else int(payload.get("address", 0x40))
    register = int(payload.get("register", 0))
    with SMBus(bus_id) as bus:
        if operation == "read":
            value = bus.read_byte_data(address, register)
            return {
                "protocol": "i2c",
                "target": target,
                "operation": operation,
                "bus": bus_id,
                "address": hex(address),
                "register": register,
                "value": value,
            }
        if operation == "write":
            value = int(payload["value"])
            bus.write_byte_data(address, register, value)
            return {
                "protocol": "i2c",
                "target": target,
                "operation": operation,
                "bus": bus_id,
                "address": hex(address),
                "register": register,
                "value": value,
                "written": True,
            }
    raise ValueError(f"Unsupported I2C operation '{operation}'")


def _parse_socket_target(target: str) -> SocketTarget:
    if "://" in target:
        parsed = urlparse(target)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port
    else:
        host, _, port_text = target.rpartition(":")
        if not host:
            raise ValueError(f"Expected host:port target, got '{target}'")
        port = int(port_text)
    if port is None:
        raise ValueError(f"Missing port in target '{target}'")
    return SocketTarget(host=host, port=port)


def _payload_to_bytes(operation: str, payload: dict[str, Any]) -> bytes:
    if "raw" in payload:
        raw = payload["raw"]
        return raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
    body = json.dumps({"operation": operation, "payload": payload})
    return body.encode("utf-8")


def _optional_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False
