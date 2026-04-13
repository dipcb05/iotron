# Vendor Data

The `vendor/` directory stores IoTron's local runtime data and operational artifacts.

## Active Storage Backend

IoTron uses SQLite as the active local backend:

- `iotron_state.db`: primary runtime database
- `backups/`: point-in-time copies created by the backup workflow

The SQLite database is the source of truth for:

- installed packages
- device inventory
- telemetry events
- deployment history
- audit events
- tenants
- RBAC policies
- revoked tokens
- notification channels

## Database Tables

`vendor/iotron_state.db` includes these tables:

- `packages`
- `devices`
- `telemetry`
- `deployments`
- `audit_log`
- `tenants`
- `rbac_policies`
- `revoked_tokens`
- `notification_channels`

## Legacy Import Files

Older JSON-backed installs may still contain these files:

- `installed_packages.db`
- `runtime_state.json`

They are now treated as legacy bootstrap sources only. On startup, IoTron can import them into SQLite if the database is empty, but live reads and writes use `vendor/iotron_state.db`.

## Operational Notes

- SQLite runs with WAL mode enabled for safer concurrent local access.
- Backups should copy both `config.json` and `vendor/iotron_state.db`.
- Secrets should not be stored here unless you intentionally use `vendor/secrets.json` via `IOTRON_SECRET_FILE`.
