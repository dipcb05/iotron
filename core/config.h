#ifndef IOTRON_CORE_CONFIG_H
#define IOTRON_CORE_CONFIG_H

#include <cstddef>
#include <string>
#include <vector>

namespace iotron {

struct DeviceProfile {
    std::string family;
    std::string name;
    std::string architecture;
    std::string sdk;
    std::string flash_protocol;
    bool supports_ota;
    std::vector<std::string> capabilities;
};

struct ProtocolProfile {
    std::string name;
    std::string category;
    std::string transport;
    bool full_duplex;
    std::size_t max_payload_bytes;
    std::vector<std::string> features;
};

struct NetworkTransport {
    std::string name;
    std::string scheme;
    int default_port;
    bool secure_by_default;
    std::vector<std::string> features;
};

struct StorageBackend {
    std::string name;
    std::string driver;
    std::string path;
    std::string retention_policy;
    bool durable;
};

struct RuntimeManifest {
    std::vector<DeviceProfile> devices;
    std::vector<ProtocolProfile> protocols;
    std::vector<NetworkTransport> networks;
    StorageBackend storage;
};

DeviceProfile arduino_uno_profile();
DeviceProfile arduino_nano_profile();
DeviceProfile arduino_mega_profile();
DeviceProfile arduino_due_profile();
DeviceProfile arduino_mkr1000_profile();
DeviceProfile esp8266_profile();
DeviceProfile esp32_profile();
DeviceProfile esp32c3_profile();
DeviceProfile esp32s2_profile();
DeviceProfile esp32s3_profile();
DeviceProfile jetson_nano_profile();
DeviceProfile jetson_tx2_profile();
DeviceProfile jetson_orin_profile();
DeviceProfile jetson_agx_xavier_profile();
DeviceProfile teensy_lc_profile();
DeviceProfile teensy3_profile();
DeviceProfile teensy4_profile();
DeviceProfile stm32_profile();
DeviceProfile raspberry_pi3_profile();
DeviceProfile beaglebone_black_profile();

ProtocolProfile i2c_profile();
ProtocolProfile spi_profile();
ProtocolProfile uart_profile();
ProtocolProfile can_profile();
ProtocolProfile modbus_profile();

NetworkTransport mqtt_transport();
NetworkTransport http_transport();
NetworkTransport websocket_transport();
NetworkTransport coap_transport();
NetworkTransport grpc_transport();

StorageBackend sqlite_storage_backend();
std::string sqlite_schema();
std::string telemetry_insert_statement(
    const std::string& device_id,
    const std::string& metric,
    const std::string& value,
    const std::string& recorded_at);
bool append_sql_journal(const std::string& journal_path, const std::string& statement);

RuntimeManifest build_default_runtime();
std::string export_runtime_manifest_json(const RuntimeManifest& manifest);
bool write_runtime_manifest(const RuntimeManifest& manifest, const std::string& output_path);

}  // namespace iotron

#endif
