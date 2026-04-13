"""FastAPI app for IoTron control-plane operations."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    load_security_settings,
    require_device_identity,
    require_operator,
)
from .service import IoTronService

APP_ROOT = Path(__file__).resolve().parent
DASHBOARD_ROOT = APP_ROOT / "dashboard"
ASSET_ROOT = DASHBOARD_ROOT / "assets"

app = FastAPI(title="IoTron API", version="0.3.0")
service = IoTronService()
security_settings = load_security_settings()

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=security_settings.requests_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "X-Device-Token", "Authorization", "Content-Type"],
)
app.mount("/dashboard/assets", StaticFiles(directory=ASSET_ROOT), name="dashboard-assets")


class PackageRequest(BaseModel):
    package: str = Field(..., min_length=1)
    version: str = "latest"


class NameRequest(BaseModel):
    name: str = Field(..., min_length=1)


class TenantRequest(BaseModel):
    tenant_id: str = Field(..., min_length=2)
    name: str = Field(..., min_length=2)


class RBACPolicyRequest(BaseModel):
    role: str = Field(..., min_length=2)
    permissions: list[str] = Field(default_factory=list)


class TokenRevokeRequest(BaseModel):
    token: str = Field(..., min_length=16)
    reason: str = Field(default="manual_revocation", min_length=3)


class ExternalTokenExchangeRequest(BaseModel):
    token: str = Field(..., min_length=16)


class NotificationChannelRequest(BaseModel):
    channel_id: str = Field(..., min_length=2)
    channel_type: str = Field(..., min_length=2)
    target: str = Field(..., min_length=2)
    enabled: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)


class BackupRestoreRequest(BaseModel):
    backup_id: str = Field(..., min_length=4)


class TokenRequest(BaseModel):
    subject: str = Field(..., min_length=2)
    role: str = Field(default="admin", min_length=4)


class DeviceRequest(BaseModel):
    device_id: str = Field(..., min_length=2)
    board: str = Field(..., min_length=2)
    protocol: str | None = None
    network: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class DeviceHeartbeatRequest(BaseModel):
    device_id: str = Field(..., min_length=2)


class DeviceDeploymentConfirmation(BaseModel):
    device_id: str = Field(..., min_length=2)
    status: str = Field(..., min_length=2)
    details: dict[str, object] = Field(default_factory=dict)


class FlashRequest(BaseModel):
    board: str = Field(..., min_length=2)
    artifact: str = Field(..., min_length=1)
    port: str | None = None
    fqbn: str | None = None
    execute: bool = False
    rollout: dict[str, object] = Field(default_factory=dict)
    rollback_artifact: str | None = None


class OTARequest(BaseModel):
    board: str = Field(..., min_length=2)
    artifact: str = Field(..., min_length=1)
    host: str = Field(..., min_length=2)
    username: str = "iotron"
    destination: str = "/opt/iotron/ota"
    execute: bool = False
    rollout: dict[str, object] = Field(default_factory=dict)
    rollback_artifact: str | None = None


class HardwareValidationRequest(BaseModel):
    board: str = Field(..., min_length=2)
    artifact: str = Field(..., min_length=1)
    port: str | None = None
    fqbn: str | None = None
    host: str | None = None
    async_job: bool = False


class WorkerClaimRequest(BaseModel):
    worker_id: str = Field(..., min_length=2)


class WorkerCompleteRequest(BaseModel):
    result: dict[str, object] | None = None
    error: str | None = None


class ProtocolExchangeRequest(BaseModel):
    protocol: str = Field(..., min_length=2)
    target: str = Field(..., min_length=2)
    operation: str = Field(..., min_length=2)
    payload: dict[str, object] = Field(default_factory=dict)


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


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(service.metrics_export(), media_type="text/plain; version=0.0.4")


@app.get("/logs")
def logs(limit: int = 100, identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.get_logs(limit=limit)


@app.get("/traces")
def traces(limit: int = 100, identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.get_traces(limit=limit)


@app.get("/alerts")
def alerts(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.get_alerts()


@app.post("/alerts/dispatch")
def alerts_dispatch(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.dispatch_notifications(actor=str(identity["sub"]))


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_ROOT / "index.html")


@app.get("/dashboard/data")
def dashboard_data() -> dict[str, object]:
    return service.dashboard_data()


@app.post("/auth/token")
def auth_token(payload: TokenRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, str]:
    return service.issue_operator_token(payload.subject, role=payload.role, actor=str(identity["sub"]))


@app.post("/auth/revoke")
def auth_revoke(payload: TokenRevokeRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.revoke_token(payload.token, reason=payload.reason, actor=str(identity["sub"]))


@app.post("/auth/exchange-external")
def auth_exchange_external(payload: ExternalTokenExchangeRequest) -> dict[str, object]:
    try:
        return service.exchange_external_identity(payload.token, actor="external-idp")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/backend/overview")
def backend_overview() -> dict[str, object]:
    return service.backend_overview()


@app.get("/security/metadata")
def security_metadata(identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.security_metadata()


@app.get("/identity/discovery")
def identity_discovery(identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.oidc_discovery()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/native/manifest")
def native_manifest() -> dict[str, object]:
    return service.runtime_manifest()


@app.get("/catalog/boards")
def boards(family: str | None = None) -> list[dict[str, str]]:
    return service.list_boards(family=family)


@app.get("/catalog/protocols")
def protocols() -> dict[str, dict[str, str]]:
    return service.list_protocols()


@app.get("/protocols/capabilities")
def protocol_capabilities() -> dict[str, dict[str, object]]:
    return service.protocol_capabilities()


@app.post("/protocols/exchange")
def protocol_exchange(payload: ProtocolExchangeRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.protocol_exchange(
            protocol=payload.protocol,
            target=payload.target,
            operation=payload.operation,
            payload=payload.payload,
            actor=str(identity["sub"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.get("/tenants")
def tenants(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.list_tenants()


@app.post("/tenants")
def create_tenant(payload: TenantRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.create_tenant(payload.tenant_id, payload.name, actor=str(identity["sub"]))


@app.get("/rbac/policies")
def rbac_policies(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.list_rbac_policies()


@app.post("/rbac/policies")
def set_rbac(payload: RBACPolicyRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.set_rbac_policy(payload.role, payload.permissions, actor=str(identity["sub"]))


@app.get("/notifications/channels")
def notification_channels(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.list_notification_channels()


@app.post("/notifications/channels")
def create_notification(
    payload: NotificationChannelRequest,
    identity: dict[str, object] = Depends(require_operator),
) -> dict[str, object]:
    return service.create_notification_channel(
        channel_id=payload.channel_id,
        channel_type=payload.channel_type,
        target=payload.target,
        enabled=payload.enabled,
        metadata=payload.metadata,
        actor=str(identity["sub"]),
    )


@app.get("/deployments")
def deployments(limit: int = 100) -> list[dict[str, object]]:
    return service.list_deployments(limit=limit)


@app.get("/jobs")
def jobs(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.list_jobs()


@app.get("/workers/metadata")
def workers_metadata(identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.worker_metadata()


@app.post("/workers/claim")
def workers_claim(payload: WorkerClaimRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object] | None:
    return service.claim_job(payload.worker_id)


@app.post("/jobs/{job_id}/complete")
def complete_job(job_id: str, payload: WorkerCompleteRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.complete_job(job_id, result=payload.result, error=payload.error)


@app.get("/jobs/{job_id}")
def job(job_id: str, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.get_job(job_id)


@app.get("/audit")
def audit(limit: int = 100, identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.list_audit_events(limit=limit)


@app.get("/backups")
def backups(identity: dict[str, object] = Depends(require_operator)) -> list[dict[str, object]]:
    return service.list_backups()


@app.post("/backups")
def backup(identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.create_backup(actor=str(identity["sub"]))


@app.post("/backups/restore")
def backup_restore(payload: BackupRestoreRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.restore_backup(payload.backup_id, actor=str(identity["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/dr/plan")
def dr_plan(identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.disaster_recovery_plan()


@app.post("/devices/register")
def register_device(payload: DeviceRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.register_device(
            device_id=payload.device_id,
            board=payload.board,
            protocol=payload.protocol,
            network=payload.network,
            metadata=payload.metadata,
            actor=str(identity["sub"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/devices/heartbeat")
def heartbeat_device(
    payload: DeviceHeartbeatRequest,
    identity: dict[str, object] = Depends(require_device_identity),
) -> dict[str, object]:
    if identity.get("device_id") != payload.device_id:
        raise HTTPException(status_code=403, detail="Device token does not match requested device")
    try:
        return service.heartbeat_device(payload.device_id, actor=str(identity["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/devices/deployment-confirmation")
def device_deployment_confirmation(
    payload: DeviceDeploymentConfirmation,
    identity: dict[str, object] = Depends(require_device_identity),
) -> dict[str, object]:
    if identity.get("device_id") != payload.device_id:
        raise HTTPException(status_code=403, detail="Device token does not match requested device")
    return service.confirm_device_deployment(
        payload.device_id,
        payload.status,
        details=payload.details,
        actor=str(identity["sub"]),
    )


@app.get("/telemetry")
def telemetry(device_id: str | None = None, limit: int = 100) -> list[dict[str, object]]:
    return service.list_telemetry(device_id=device_id, limit=limit)


@app.post("/telemetry")
def ingest_telemetry(
    payload: TelemetryRequest,
    identity: dict[str, object] = Depends(require_device_identity),
) -> dict[str, object]:
    if identity.get("device_id") != payload.device_id:
        raise HTTPException(status_code=403, detail="Device token does not match requested device")
    try:
        return service.ingest_telemetry(
            device_id=payload.device_id,
            metric=payload.metric,
            value=payload.value,
            recorded_at=payload.recorded_at,
            actor=str(identity["sub"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/packages/install")
def install_package(payload: PackageRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, str]:
    return service.install_package(payload.package, payload.version, actor=str(identity["sub"]))


@app.post("/packages/uninstall")
def uninstall_package(payload: NameRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return {"removed": service.uninstall_package(payload.name, actor=str(identity["sub"])), "package": payload.name}


@app.post("/packages/update")
def update_package(payload: PackageRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, str]:
    return service.update_package(payload.package, payload.version, actor=str(identity["sub"]))


@app.get("/project/state")
def project_state() -> dict[str, object]:
    return service.status()


@app.post("/project/select-board")
def select_board(payload: NameRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.select_board(payload.name, actor=str(identity["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/enable-protocol")
def enable_protocol(payload: NameRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.enable_protocol(payload.name, actor=str(identity["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/enable-network")
def enable_network(payload: NameRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.enable_network(payload.name, actor=str(identity["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/web/install")
def install_dashboard(identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.install_web_dashboard(actor=str(identity["sub"]))


@app.post("/project/flash")
def flash(payload: FlashRequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.flash_firmware(
            board=payload.board,
            artifact=payload.artifact,
            port=payload.port,
            fqbn=payload.fqbn,
            execute=payload.execute,
            rollout=payload.rollout or None,
            rollback_artifact=payload.rollback_artifact,
            actor=str(identity["sub"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/ota")
def ota(payload: OTARequest, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    try:
        return service.ota_update(
            board=payload.board,
            artifact=payload.artifact,
            host=payload.host,
            username=payload.username,
            destination=payload.destination,
            execute=payload.execute,
            rollout=payload.rollout or None,
            rollback_artifact=payload.rollback_artifact,
            actor=str(identity["sub"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/project/prune")
def prune_runtime(limit: int = 1000, identity: dict[str, object] = Depends(require_operator)) -> dict[str, object]:
    return service.prune_runtime_data(retain_latest_per_device=limit, actor=str(identity["sub"]))


@app.post("/project/hardware-validate")
def hardware_validate(
    payload: HardwareValidationRequest,
    identity: dict[str, object] = Depends(require_operator),
) -> dict[str, object]:
    if payload.async_job:
        return service.schedule_hardware_validation(
            board=payload.board,
            artifact=payload.artifact,
            port=payload.port,
            fqbn=payload.fqbn,
            host=payload.host,
            actor=str(identity["sub"]),
        )
    try:
        return service.validate_hardware(
            board=payload.board,
            artifact=payload.artifact,
            port=payload.port,
            fqbn=payload.fqbn,
            host=payload.host,
            actor=str(identity["sub"]),
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
