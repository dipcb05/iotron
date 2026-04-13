"""Catalogs for supported boards, protocols, and network transports."""

from __future__ import annotations

from collections import OrderedDict

BOARD_FAMILIES = OrderedDict(
    {
        "arduino": [
            "uno",
            "nano",
            "mega",
            "due",
            "mkr1000",
        ],
        "espressif": [
            "esp8266",
            "esp32",
            "esp32c3",
            "esp32s2",
            "esp32s3",
        ],
        "jetson": [
            "nano",
            "tx2",
            "orin",
            "agx-xavier",
        ],
        "teensy": [
            "teensy-lc",
            "teensy3",
            "teensy4",
        ],
        "stm32": [
            "stm32",
        ],
        "raspberrypi": [
            "raspberry-pi-3",
        ],
        "beaglebone": [
            "beaglebone-black",
        ],
    }
)

PROTOCOLS = {
    "i2c": {
        "type": "embedded-bus",
        "description": "Short-distance peripheral communication for sensors and controllers.",
    },
    "spi": {
        "type": "embedded-bus",
        "description": "High-speed synchronous peripheral bus for displays, storage, and radios.",
    },
    "uart": {
        "type": "embedded-bus",
        "description": "Serial communication channel commonly used for debugging and peripheral links.",
    },
    "can": {
        "type": "embedded-bus",
        "description": "Deterministic bus for industrial and automotive systems.",
    },
    "modbus": {
        "type": "industrial",
        "description": "Industrial field communication for PLCs, meters, and controllers.",
    },
}

NETWORKS = {
    "mqtt": {
        "type": "iot-network",
        "description": "Publish-subscribe messaging for telemetry and device state.",
    },
    "http": {
        "type": "web",
        "description": "REST integrations for web services and management APIs.",
    },
    "websocket": {
        "type": "web",
        "description": "Bidirectional real-time stream for dashboards and operators.",
    },
    "coap": {
        "type": "iot-network",
        "description": "Lightweight constrained-device application protocol.",
    },
    "grpc": {
        "type": "service-mesh",
        "description": "Low-latency service-to-service RPC for edge orchestration.",
    },
}


def list_boards() -> list[dict[str, str]]:
    boards: list[dict[str, str]] = []
    for family, names in BOARD_FAMILIES.items():
        for name in names:
            boards.append({"family": family, "name": name})
    return boards
