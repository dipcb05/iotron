"""FastAPI app for IoTron control-plane operations."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .security import RateLimitMiddleware, SecurityHeadersMiddleware, load_security_settings, require_api_key
from .service import IoTronService

APP_ROOT = Path(__file__).resolve().parent
DASHBOARD_ROOT = APP_ROOT / "dashboard"
ASSET_ROOT = DASHBOARD_ROOT / "assets"

app = FastAPI(title="IoTron API", version="0.2.0")
service = IoTronService()
security_settings = load_security_settings()

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=security_settings.requests_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)
app.mount("/dashboard/assets", StaticFiles(directory=ASSET_ROOT), name="dashboard-assets")


class PackageRequest(BaseModel):
    package: str = Field(..., min_length=1)
    version: str = "latest"


class NameRequest(BaseModel):
    name: str = Field(..., min_length=1)


class DeviceRequest(BaseModel):
    device_id: str = Field(..., min_length=2)
    board: str = Field(..., min_length=2)
    protocol: str | None = None
    network: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class DeviceHeartbeatRequest(BaseModel):
    device_id: str = Field(..., min_length=2)


class FlashRequest(BaseModel):
    board: str = Field(..., min_length=2)
    artifact: str = Field(..., min_length=1)
    port: str | None = None
    fqbn: str | None = None
    execute: bool = False


class OTARequest(BaseModel):
    board: str = Field(..., min_length=2)
    artifact: str = Field(..., min_length=1)
    host: str = Field(..., min_length=2)
    username: str = "iotron"
    destination: str = "/opt/iotron/ota"
    execute: bool = False


class AIPlanRequest(BaseModel):
    goal: str = Field(..., min_length=5)
    board: str | None = None
    protocols: list[str] = Field(default_factory=list)
    networks: list[str] = Field(default_factory=list)


class TelemetryRequest(BaseModel):
    device_id: str = Field(..., min_length=2)
    metric: str = Field(..., min_length=1)
    value: object
    recorded_at: str | None = None


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "IoTron",
        "message": "IoTron FastAPI control plane is running.",
        "dashboard": "/dashboard",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_ROOT / "index.html")


@app.get("/dashboard/data")
def dashboard_data() -> dict[str, object]:
    return service.dashboard_data()


@app.get("/backend/overview")
def backend_overview() -> dict[str, object]:
    return service.backend_overview()


@app.get("/native/manifest")
def native_manifest() -> dict[str, object]:
    return service.runtime_manifest()


@app.get("/catalog/boards")
def boards(family: str | None = None) -> list[dict[str, str]]:
    return service.list_boards(family=family)


@app.get("/catalog/protocols")
def protocols() -> dict[str, dict[str, str]]:
    return service.list_protocols()


@app.get("/catalog/networks")
def networks() -> dict[str, dict[str, str]]:
    return service.list_networks()


@app.get("/catalog/toolchains")
def toolchains() -> list[dict[str, object]]:
    return service.list_toolchains()


@app.get("/packages")
def packages() -> list[dict[str, str]]:
    return service.list_packages()


@app.get("/devices")
def devices() -> list[dict[str, object]]:
    return service.list_devices()


@app.post("/devices/register", dependencies=[Depends(require_api_key)])
def register_device(payload: DeviceRequest) -> dict[str, object]:
    try:
        return service.register_device(
            device_id=payload.device_id,
            board=payload.board,
            protocol=payload.protocol,
            network=payload.network,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/devices/heartbeat", dependencies=[Depends(require_api_key)])
def heartbeat_device(payload: DeviceHeartbeatRequest) -> dict[str, object]:
    try:
        return service.heartbeat_device(payload.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/telemetry")
def telemetry(device_id: str | None = None, limit: int = 100) -> list[dict[str, object]]:
    return service.list_telemetry(device_id=device_id, limit=limit)


@app.post("/telemetry", dependencies=[Depends(require_api_key)])
def ingest_telemetry(payload: TelemetryRequest) -> dict[str, object]:
    try:
        return service.ingest_telemetry(
            device_id=payload.device_id,
            metric=payload.metric,
            value=payload.value,
            recorded_at=payload.recorded_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/packages/install", dependencies=[Depends(require_api_key)])
def install_package(payload: PackageRequest) -> dict[str, str]:
    return service.install_package(payload.package, payload.version)


@app.post("/packages/uninstall", dependencies=[Depends(require_api_key)])
def uninstall_package(payload: NameRequest) -> dict[str, object]:
    return {"removed": service.uninstall_package(payload.name), "package": payload.name}


@app.post("/packages/update", dependencies=[Depends(require_api_key)])
def update_package(payload: PackageRequest) -> dict[str, str]:
    return service.update_package(payload.package, payload.version)


@app.get("/project/state")
def project_state() -> dict[str, object]:
    return service.status()


@app.post("/project/select-board", dependencies=[Depends(require_api_key)])
def select_board(payload: NameRequest) -> dict[str, object]:
    try:
        return service.select_board(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/enable-protocol", dependencies=[Depends(require_api_key)])
def enable_protocol(payload: NameRequest) -> dict[str, object]:
    try:
        return service.enable_protocol(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/enable-network", dependencies=[Depends(require_api_key)])
def enable_network(payload: NameRequest) -> dict[str, object]:
    try:
        return service.enable_network(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/web/install", dependencies=[Depends(require_api_key)])
def install_dashboard() -> dict[str, object]:
    return service.install_web_dashboard()


@app.post("/project/flash", dependencies=[Depends(require_api_key)])
def flash(payload: FlashRequest) -> dict[str, object]:
    try:
        return service.flash_firmware(
            board=payload.board,
            artifact=payload.artifact,
            port=payload.port,
            fqbn=payload.fqbn,
            execute=payload.execute,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/ota", dependencies=[Depends(require_api_key)])
def ota(payload: OTARequest) -> dict[str, object]:
    try:
        return service.ota_update(
            board=payload.board,
            artifact=payload.artifact,
            host=payload.host,
            username=payload.username,
            destination=payload.destination,
            execute=payload.execute,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/dashboard/summary")
def dashboard_summary() -> dict[str, object]:
    return service.dashboard_summary()


@app.post("/ai/plan")
def ai_plan(payload: AIPlanRequest) -> dict[str, object]:
    return service.ai_plan(
        goal=payload.goal,
        board=payload.board,
        protocols=payload.protocols,
        networks=payload.networks,
    )
