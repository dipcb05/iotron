#include "../config.h"

#include <fstream>

namespace iotron {

StorageBackend sqlite_storage_backend() {
    return StorageBackend{
        "sqlite-local",
        "sqlite3",
        "vendor/iotron_runtime.db",
        "30 days hot telemetry with manifest journaling",
        true,
    };
}

std::string sqlite_schema() {
    return
        "CREATE TABLE IF NOT EXISTS devices ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "device_id TEXT NOT NULL UNIQUE,"
        "family TEXT NOT NULL,"
        "board_name TEXT NOT NULL,"
        "firmware_version TEXT,"
        "last_seen_utc TEXT,"
        "metadata_json TEXT DEFAULT '{}');"
        "CREATE TABLE IF NOT EXISTS telemetry ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "device_id TEXT NOT NULL,"
        "metric TEXT NOT NULL,"
        "value TEXT NOT NULL,"
        "recorded_at_utc TEXT NOT NULL);";
}

std::string telemetry_insert_statement(
    const std::string& device_id,
    const std::string& metric,
    const std::string& value,
    const std::string& recorded_at) {
    return "INSERT INTO telemetry(device_id, metric, value, recorded_at_utc) VALUES('" +
           device_id + "', '" + metric + "', '" + value + "', '" + recorded_at + "');";
}

bool append_sql_journal(const std::string& journal_path, const std::string& statement) {
    std::ofstream out(journal_path.c_str(), std::ios::app);
    if (!out) {
        return false;
    }
    out << statement << '\n';
    return static_cast<bool>(out);
}

}  // namespace iotron
