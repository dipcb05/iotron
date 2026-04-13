# IoTron

IoTron is an open-source IoT framework for building device-to-cloud workflows across embedded boards and edge systems. The repository includes a Python control plane, a FastAPI backend, a browser operations console, production-oriented flashing and OTA workflows, a native runtime execution layer in `core/`, and Python/Go integration surfaces.


## Implemented Surfaces

- Python CLI for package, board, protocol, network, flash, OTA, and AI planning workflows
- FastAPI control plane with dashboard, catalog, device registry, telemetry ingestion, flashing, OTA, package, and planning endpoints
- Static dashboard UI served from FastAPI at `/dashboard`
- Board toolchain integration with artifact validation, staged rollout metadata, rollback targets, signing, and health-confirmation workflow support
- Native `core/` runtime layer with device lifecycle supervision, protocol sessions, network sessions, buffering, retry policy, storage descriptors, and a C ABI for shared-library builds
- Native Python and Go binding glue for compiled-library integration
- CI, release, and security workflows for GitHub Actions
- Operator/device bearer tokens, API key compatibility, audit logging, rate limiting, CORS control, and security headers
- SQLite-backed persistence for packages, devices, telemetry, deployments, audit trails, tenancy, and RBAC

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

## Storage Model

IoTron uses `vendor/iotron_state.db` as the active local backend. The database stores:

- packages
- devices
- telemetry
- deployments
- audit records
- tenants
- RBAC policies
- revoked tokens
- notification channels

Legacy files such as `vendor/installed_packages.db` and `vendor/runtime_state.json` are import-only compatibility sources for older installs. They are not the active persistence layer.

The vendor directory is documented in [vendor/README.md](vendor/README.md).

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
- `GET /dashboard/summary`
- `GET /backend/overview`
- `GET /native/manifest`
- `POST /auth/token`
- `POST /auth/revoke`
- `GET /security/metadata`
- `GET /catalog/boards`
- `GET /catalog/protocols`
- `GET /catalog/networks`
- `GET /catalog/toolchains`
- `GET /devices`
- `POST /devices/register`
- `POST /devices/heartbeat`
- `POST /devices/deployment-confirmation`
- `GET /telemetry`
- `POST /telemetry`
- `GET /deployments`
- `GET /audit`
- `GET /metrics`
- `GET /logs`
- `GET /traces`
- `GET /alerts`
- `POST /alerts/dispatch`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /backups`
- `POST /backups`
- `POST /backups/restore`
- `GET /dr/plan`
- `GET /tenants`
- `POST /tenants`
- `GET /rbac/policies`
- `POST /rbac/policies`
- `GET /notifications/channels`
- `POST /notifications/channels`
- `POST /project/flash`
- `POST /project/ota`
- `POST /project/prune`
- `POST /project/hardware-validate`
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
- `IOTRON_BEARER_SECRET`: signing secret for operator and device tokens
- `IOTRON_PREVIOUS_BEARER_SECRET`: previous signing secret used during token rotation
- `IOTRON_OIDC_ISSUER`: expected issuer for external identity integration
- `IOTRON_OIDC_AUDIENCE`: expected audience for external identity integration
- `IOTRON_SECRET_FILE`: optional JSON secret file such as `vendor/secrets.json`
- `IOTRON_ALLOWED_ORIGINS`: allowed browser origins for the API
- `IOTRON_RATE_LIMIT_PER_MINUTE`: per-client request cap
- `IOTRON_TOKEN_TTL_SECONDS`: operator token lifetime
- `IOTRON_DEVICE_TOKEN_TTL_SECONDS`: device token lifetime
- `IOTRON_ARTIFACT_SIGNING_KEY`: signing key for deployment artifact manifests
- `IOTRON_NATIVE_LIB`: compiled native library path for Python binding use

CI and release automation live in `.github/workflows/`.

## Vendor Layout

```text
vendor/
  iotron_state.db
  backups/
  README.md
```

Optional legacy compatibility files may appear during migration, but the SQLite database is the authoritative store.

## Backend SDKs

- FastAPI is the primary backend API layer and now exposes operator auth, device registry, telemetry ingestion, deployment tracking, audit logs, backend overview, and runtime manifest endpoints.
- Go support lives in [bindings/go/iotron.go](bindings/go/iotron.go) as a backend client for health checks, state, auth token issuance, deployments, toolchains, device registration, telemetry, flash, and OTA operations.
- Python native binding helpers live in [bindings/python/iotron.py](bindings/python/iotron.py) and can load a compiled shared library via `IOTRON_NATIVE_LIB`.

## Native Runtime

The `core/` directory now exports a runtime model for:

- board/device descriptors and lifecycle supervision
- embedded protocol session descriptors
- network transport session descriptors
- runtime buffering and retry policy models
- SQLite storage schema and journaling helpers
- C ABI entry points in `core/c_api.h` and `core/c_api.cpp`

Native builds:

- `CMakeLists.txt` provides a shared-library build target for environments with CMake and a C++ compiler.
- `scripts/build_native.py` provides a direct build path for `g++`, `clang++`, or MSVC `cl`.

The native runtime, shared-library interfaces, and board integration workflow are built around the backend control plane and SQLite vendor store. Hardware validation and vendor-tool execution still depend on the toolchains and devices installed in the target environment.

## Roadmap

The next areas of expansion for the framework are:

- actual hardware flashing execution in CI with board-specific integration tests and connected devices
- end-to-end protocol I/O against real buses and brokers, beyond lifecycle/session supervision
- signed OTA rollout workflow and artifact verification
- richer identity integration such as RBAC backed by OIDC or external IAM
- deeper live integration with external IdPs and distributed worker infrastructure
