#include "config.h"

#include <fstream>
#include <sstream>

namespace iotron {
namespace {

std::string json_escape(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (char ch : value) {
        switch (ch) {
            case '\\': escaped += "\\\\"; break;
            case '"': escaped += "\\\""; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default: escaped += ch; break;
        }
    }
    return escaped;
}

std::string quote(const std::string& value) {
    return "\"" + json_escape(value) + "\"";
}

std::string stringify_list(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index > 0) {
            out << ", ";
        }
        out << quote(values[index]);
    }
    out << "]";
    return out.str();
}

}  // namespace

RuntimeManifest build_default_runtime() {
    RuntimeManifest manifest;
    manifest.devices = {
        arduino_uno_profile(),
        arduino_nano_profile(),
        arduino_mega_profile(),
        arduino_due_profile(),
        arduino_mkr1000_profile(),
        esp8266_profile(),
        esp32_profile(),
        esp32c3_profile(),
        esp32s2_profile(),
        esp32s3_profile(),
        jetson_nano_profile(),
        jetson_tx2_profile(),
        jetson_orin_profile(),
        jetson_agx_xavier_profile(),
        teensy_lc_profile(),
        teensy3_profile(),
        teensy4_profile(),
        stm32_profile(),
        raspberry_pi3_profile(),
        beaglebone_black_profile(),
    };
    manifest.protocols = {
        i2c_profile(),
        spi_profile(),
        uart_profile(),
        can_profile(),
        modbus_profile(),
    };
    manifest.networks = {
        mqtt_transport(),
        http_transport(),
        websocket_transport(),
        coap_transport(),
        grpc_transport(),
    };
    manifest.storage = sqlite_storage_backend();
    return manifest;
}

std::string export_runtime_manifest_json(const RuntimeManifest& manifest) {
    std::ostringstream out;
    out << "{\n  \"devices\": [\n";
    for (std::size_t index = 0; index < manifest.devices.size(); ++index) {
        const DeviceProfile& device = manifest.devices[index];
        out << "    {"
            << "\"family\": " << quote(device.family) << ", "
            << "\"name\": " << quote(device.name) << ", "
            << "\"architecture\": " << quote(device.architecture) << ", "
            << "\"sdk\": " << quote(device.sdk) << ", "
            << "\"flash_protocol\": " << quote(device.flash_protocol) << ", "
            << "\"supports_ota\": " << (device.supports_ota ? "true" : "false") << ", "
            << "\"capabilities\": " << stringify_list(device.capabilities)
            << "}";
        out << (index + 1 == manifest.devices.size() ? "\n" : ",\n");
    }

    out << "  ],\n  \"protocols\": [\n";
    for (std::size_t index = 0; index < manifest.protocols.size(); ++index) {
        const ProtocolProfile& protocol = manifest.protocols[index];
        out << "    {"
            << "\"name\": " << quote(protocol.name) << ", "
            << "\"category\": " << quote(protocol.category) << ", "
            << "\"transport\": " << quote(protocol.transport) << ", "
            << "\"full_duplex\": " << (protocol.full_duplex ? "true" : "false") << ", "
            << "\"max_payload_bytes\": " << protocol.max_payload_bytes << ", "
            << "\"features\": " << stringify_list(protocol.features)
            << "}";
        out << (index + 1 == manifest.protocols.size() ? "\n" : ",\n");
    }

    out << "  ],\n  \"networks\": [\n";
    for (std::size_t index = 0; index < manifest.networks.size(); ++index) {
        const NetworkTransport& network = manifest.networks[index];
        out << "    {"
            << "\"name\": " << quote(network.name) << ", "
            << "\"scheme\": " << quote(network.scheme) << ", "
            << "\"default_port\": " << network.default_port << ", "
            << "\"secure_by_default\": " << (network.secure_by_default ? "true" : "false") << ", "
            << "\"features\": " << stringify_list(network.features)
            << "}";
        out << (index + 1 == manifest.networks.size() ? "\n" : ",\n");
    }

    out << "  ],\n  \"storage\": {"
        << "\"name\": " << quote(manifest.storage.name) << ", "
        << "\"driver\": " << quote(manifest.storage.driver) << ", "
        << "\"path\": " << quote(manifest.storage.path) << ", "
        << "\"retention_policy\": " << quote(manifest.storage.retention_policy) << ", "
        << "\"durable\": " << (manifest.storage.durable ? "true" : "false")
        << "}\n}";
    return out.str();
}

bool write_runtime_manifest(const RuntimeManifest& manifest, const std::string& output_path) {
    std::ofstream out(output_path.c_str(), std::ios::out | std::ios::trunc);
    if (!out) {
        return false;
    }
    out << export_runtime_manifest_json(manifest) << '\n';
    return static_cast<bool>(out);
}

}  // namespace iotron
