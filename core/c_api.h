#ifndef IOTRON_C_API_H
#define IOTRON_C_API_H

#ifdef __cplusplus
extern "C" {
#endif

const char* iotron_manifest_json();
const char* iotron_runtime_summary_json();
const char* iotron_runtime_supervisor_json();
const char* iotron_sqlite_schema();
const char* iotron_telemetry_insert_sql(
    const char* device_id,
    const char* metric,
    const char* value,
    const char* recorded_at);
void iotron_free_string(const char* value);

#ifdef __cplusplus
}
#endif

#endif
