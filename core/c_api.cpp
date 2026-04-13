#include "c_api.h"
#include "config.h"

#include <cstring>
#include <sstream>
#include <string>

namespace {

char* duplicate_string(const std::string& value) {
    char* result = new char[value.size() + 1];
    std::memcpy(result, value.c_str(), value.size() + 1);
    return result;
}

std::string runtime_summary_json() {
    const iotron::RuntimeManifest manifest = iotron::build_default_runtime();
    std::ostringstream out;
    out << "{"
        << "\"devices\": " << manifest.devices.size() << ", "
        << "\"protocols\": " << manifest.protocols.size() << ", "
        << "\"networks\": " << manifest.networks.size() << ", "
        << "\"storage\": \"" << manifest.storage.name << "\""
        << "}";
    return out.str();
}

std::string value_or_empty(const char* value) {
    return value == nullptr ? std::string() : std::string(value);
}

} 

extern "C" {

const char* iotron_manifest_json() {
    return duplicate_string(iotron::export_runtime_manifest_json(iotron::build_default_runtime()));
}

const char* iotron_runtime_summary_json() {
    return duplicate_string(runtime_summary_json());
}

const char* iotron_runtime_supervisor_json() {
    return duplicate_string(export_runtime_supervisor_json(create_runtime_supervisor(build_default_runtime())));
}

const char* iotron_sqlite_schema() {
    return duplicate_string(iotron::sqlite_schema());
}

const char* iotron_telemetry_insert_sql(
    const char* device_id,
    const char* metric,
    const char* value,
    const char* recorded_at) {
    return duplicate_string(
        iotron::telemetry_insert_statement(
            value_or_empty(device_id),
            value_or_empty(metric),
            value_or_empty(value),
            value_or_empty(recorded_at)));
}

void iotron_free_string(const char* value) {
    delete[] value;
}

}
