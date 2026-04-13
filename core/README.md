# Core Runtime Roadmap

The `core/` directory now contains a concrete native runtime manifest layer for IoTron.

Implemented surfaces:

- device descriptors for Arduino, ESP32, Jetson, Teensy, STM32, Raspberry Pi, and BeagleBone boards
- protocol descriptors for I2C, SPI, UART, CAN, and Modbus
- network transport descriptors for MQTT, HTTP, WebSocket, CoAP, and gRPC
- SQLite schema text and append-only journaling helpers
- runtime manifest export functions for bindings and packaging

Current limitation:

- this is still descriptor-level native infrastructure, not a compiled hardware SDK with live board drivers or transport stacks
