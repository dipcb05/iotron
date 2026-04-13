CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL,
    board_name TEXT NOT NULL,
    firmware_version TEXT,
    last_seen_utc TEXT,
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value TEXT NOT NULL,
    recorded_at_utc TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
ON telemetry(device_id, recorded_at_utc);
