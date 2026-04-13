# Core Runtime

The `core/` directory contains the native runtime layer for IoTron.

Implemented surfaces:

- device descriptors for Arduino, ESP32, Jetson, Teensy, STM32, Raspberry Pi, and BeagleBone boards
- protocol descriptors for I2C, SPI, UART, CAN, and Modbus
- network transport descriptors for MQTT, HTTP, WebSocket, CoAP, and gRPC
- SQLite schema text and append-only journaling helpers
- runtime manifest export functions for bindings and packaging

Current scope:

- the current implementation focuses on runtime descriptors, exported interfaces, and storage helpers that support the first release architecture
- board-specific live drivers and transport execution layers continue to expand from this base
