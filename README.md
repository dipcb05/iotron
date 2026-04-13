# IoTron

IoTron is an open-source IoT framework for building device-to-cloud workflows across embedded boards and edge systems. The repository now includes a working Python control plane, a browser dashboard, board flashing and OTA wrappers, backend-oriented device and telemetry APIs, a populated native runtime layer in `core/`, and starter binding/CI infrastructure.

## Version

IoTron `v0.2.0` is the first release of the framework. It establishes the control plane, native runtime interfaces, backend APIs, and integration surface for board and protocol workflows.

## Implemented Surfaces

- Python CLI for package, board, protocol, network, flash, OTA, and AI planning workflows
- FastAPI control plane with dashboard, catalog, device registry, telemetry ingestion, flashing, OTA, package, and planning endpoints
- Static dashboard UI served from FastAPI at `/dashboard`
- Board toolchain integration plans for Arduino, ESP32, Teensy, STM32, Jetson, Raspberry Pi, and BeagleBone
- Native `core/` runtime layer with device, protocol, network, storage descriptors, and a C ABI for shared-library builds
- Native Python and Go binding glue for compiled-library integration
- CI, release, and security workflows for GitHub Actions
- API key protection, basic rate limiting, CORS control, and security headers

## Quick Start

```bash
pip install -r requirements.txt
python scripts/migrate_db.py
python -m iotron.cli status
python -m iotron.cli toolchains
python -m iotron.cli flash esp32 firmware.bin
python -m iotron.cli devices
python -m iotron.cli telemetry --limit 10
python scripts/build_native.py
uvicorn iotron.api:app --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000/dashboard`
- API docs: `http://127.0.0.1:8000/docs`

## CLI Commands

```text
status
boards [--family FAMILY]
protocols
networks
toolchains
devices
telemetry [--device-id DEVICE] [--limit N]
list
install PACKAGE [--version VERSION]
uninstall PACKAGE
update PACKAGE [--version VERSION]
select-board BOARD
enable-protocol PROTOCOL
enable-network NETWORK
web install
flash BOARD ARTIFACT [--port PORT] [--fqbn FQBN] [--execute]
ota BOARD ARTIFACT --host HOST [--username USER] [--destination PATH] [--execute]
build-native [--python PYTHON]
ai-plan --goal TEXT [--board BOARD]
export-config
```

## FastAPI Endpoints

- `GET /health`
- `GET /dashboard`
- `GET /dashboard/data`
- `GET /backend/overview`
- `GET /native/manifest`
- `GET /catalog/boards`
- `GET /catalog/protocols`
- `GET /catalog/networks`
- `GET /catalog/toolchains`
- `GET /devices`
- `POST /devices/register`
- `POST /devices/heartbeat`
- `GET /telemetry`
- `POST /telemetry`
- `POST /project/flash`
- `POST /project/ota`
- `POST /project/select-board`
- `POST /project/enable-protocol`
- `POST /project/enable-network`
- `POST /project/web/install`
- `POST /packages/install`
- `POST /packages/uninstall`
- `POST /packages/update`
- `POST /ai/plan`

## Security and Operations

Environment settings live in [.env.example](.env.example):

- `IOTRON_API_KEY`: protects mutation endpoints when set
- `IOTRON_ALLOWED_ORIGINS`: allowed browser origins for the API
- `IOTRON_RATE_LIMIT_PER_MINUTE`: per-client request cap
- `IOTRON_NATIVE_LIB`: compiled native library path for Python binding use

CI and release automation live in `.github/workflows/`.

## Backend SDKs

- FastAPI is the primary backend API layer and now exposes device registry, telemetry ingestion, backend overview, and runtime manifest endpoints.
- Go support lives in [bindings/go/iotron.go](bindings/go/iotron.go) as a backend client for health checks, state, toolchains, device registration, telemetry, flash, and OTA operations.
- Python native binding helpers live in [bindings/python/iotron.py](bindings/python/iotron.py) and can load a compiled shared library via `IOTRON_NATIVE_LIB`.

## Native Runtime

The `core/` directory now exports a runtime model for:

- board/device descriptors
- embedded protocol descriptors
- network transport descriptors
- SQLite storage schema and journaling helpers
- C ABI entry points in `core/c_api.h` and `core/c_api.cpp`

Native builds:

- `CMakeLists.txt` provides a shared-library build target for environments with CMake and a C++ compiler.
- `scripts/build_native.py` provides a direct build path for `g++`, `clang++`, or MSVC `cl`.

This release provides the native runtime structure, shared-library interfaces, and board integration workflow. Hardware validation and vendor-tool execution depend on the toolchains and devices installed in the target environment.

## Roadmap

The next areas of expansion for the framework are:

- actual hardware flashing execution in CI with board-specific integration tests and connected devices
- signed OTA rollout workflow and artifact verification
- authentication beyond single API key, such as RBAC or OIDC
- a full multi-page frontend dashboard with auth and device actions
