#include "config.h"

#include <algorithm>
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

bool profile_supports_protocol(const DeviceProfile& device, const ProtocolProfile& protocol) {
    return std::find(device.capabilities.begin(), device.capabilities.end(), protocol.name) != device.capabilities.end();
}

bool profile_supports_network(const DeviceProfile& device, const NetworkTransport& transport) {
    if (transport.name == "mqtt" || transport.name == "http" || transport.name == "websocket" || transport.name == "coap" || transport.name == "grpc") {
        return std::find(device.capabilities.begin(), device.capabilities.end(), "wifi") != device.capabilities.end() ||
               std::find(device.capabilities.begin(), device.capabilities.end(), "linux") != device.capabilities.end() ||
               std::find(device.capabilities.begin(), device.capabilities.end(), "docker") != device.capabilities.end() ||
               device.family == "jetson" || device.family == "raspberrypi" || device.family == "beaglebone";
    }
    return false;
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

RetryPolicy default_retry_policy() {
    return RetryPolicy{5, 250, 10000, 2.0};
}

RuntimeBuffer create_runtime_buffer(std::size_t capacity) {
    return RuntimeBuffer{capacity, std::vector<RuntimeFrame>(), 0};
}

ProtocolSession create_protocol_session(const ProtocolProfile& profile, const RetryPolicy& retry_policy) {
    return ProtocolSession{profile.name, LifecycleState::kRegistered, retry_policy, 0, "", ""};
}

NetworkSession create_network_session(const NetworkTransport& transport, const RetryPolicy& retry_policy, const std::string& endpoint) {
    return NetworkSession{transport.name, endpoint, LifecycleState::kRegistered, retry_policy, 0, "", ""};
}

DeviceRuntime create_device_runtime(
    const std::string& device_id,
    const DeviceProfile& profile,
    const std::vector<ProtocolProfile>& protocols,
    const std::vector<NetworkTransport>& networks,
    const RetryPolicy& retry_policy) {
    DeviceRuntime runtime;
    runtime.device_id = device_id;
    runtime.profile = profile;
    runtime.lifecycle = LifecycleState::kRegistered;
    runtime.outbound_buffer = create_runtime_buffer(1024);
    runtime.inbound_buffer = create_runtime_buffer(1024);
    runtime.last_heartbeat_at = "";

    for (const ProtocolProfile& protocol : protocols) {
        if (profile_supports_protocol(profile, protocol)) {
            runtime.protocol_sessions.push_back(create_protocol_session(protocol, retry_policy));
        }
    }
    for (const NetworkTransport& network : networks) {
        if (profile_supports_network(profile, network)) {
            std::ostringstream endpoint;
            endpoint << network.scheme << "://device/" << device_id << ":" << network.default_port;
            runtime.network_sessions.push_back(create_network_session(network, retry_policy, endpoint.str()));
        }
    }
    return runtime;
}

RuntimeSupervisor create_runtime_supervisor(const RuntimeManifest& manifest) {
    RuntimeSupervisor supervisor;
    supervisor.manifest = manifest;
    supervisor.retry_policy = default_retry_policy();
    for (std::size_t index = 0; index < manifest.devices.size(); ++index) {
        std::ostringstream device_id;
        device_id << manifest.devices[index].family << "-" << manifest.devices[index].name << "-" << index;
        supervisor.devices.push_back(
            create_device_runtime(
                device_id.str(),
                manifest.devices[index],
                manifest.protocols,
                manifest.networks,
                supervisor.retry_policy));
    }
    return supervisor;
}

bool enqueue_outbound_frame(DeviceRuntime& device, const RuntimeFrame& frame) {
    if (device.outbound_buffer.frames.size() >= device.outbound_buffer.capacity) {
        device.outbound_buffer.frames.erase(device.outbound_buffer.frames.begin());
        device.outbound_buffer.dropped_frames += 1;
    }
    device.outbound_buffer.frames.push_back(frame);
    return true;
}

bool enqueue_inbound_frame(DeviceRuntime& device, const RuntimeFrame& frame) {
    if (device.inbound_buffer.frames.size() >= device.inbound_buffer.capacity) {
        device.inbound_buffer.frames.erase(device.inbound_buffer.frames.begin());
        device.inbound_buffer.dropped_frames += 1;
    }
    device.inbound_buffer.frames.push_back(frame);
    return true;
}

bool mark_protocol_connected(ProtocolSession& session, const std::string& connected_at) {
    session.state = LifecycleState::kOnline;
    session.connected_at = connected_at;
    session.last_error = "";
    session.attempts = 0;
    return true;
}

bool mark_network_connected(NetworkSession& session, const std::string& heartbeat_at) {
    session.state = LifecycleState::kOnline;
    session.last_heartbeat_at = heartbeat_at;
    session.last_error = "";
    session.attempts = 0;
    return true;
}

bool mark_protocol_error(ProtocolSession& session, const std::string& error) {
    session.last_error = error;
    session.attempts += 1;
    session.state = session.attempts >= session.retry_policy.max_attempts ? LifecycleState::kOffline : LifecycleState::kRetrying;
    return session.state != LifecycleState::kOffline;
}

bool mark_network_error(NetworkSession& session, const std::string& error) {
    session.last_error = error;
    session.attempts += 1;
    session.state = session.attempts >= session.retry_policy.max_attempts ? LifecycleState::kOffline : LifecycleState::kRetrying;
    return session.state != LifecycleState::kOffline;
}

bool update_device_heartbeat(DeviceRuntime& device, const std::string& heartbeat_at) {
    device.last_heartbeat_at = heartbeat_at;
    device.lifecycle = LifecycleState::kOnline;
    return true;
}

std::string lifecycle_state_name(LifecycleState state) {
    switch (state) {
        case LifecycleState::kRegistered: return "registered";
        case LifecycleState::kConnecting: return "connecting";
        case LifecycleState::kOnline: return "online";
        case LifecycleState::kDegraded: return "degraded";
        case LifecycleState::kRetrying: return "retrying";
        case LifecycleState::kOffline: return "offline";
        default: return "unknown";
    }
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

std::string export_runtime_supervisor_json(const RuntimeSupervisor& supervisor) {
    std::ostringstream out;
    out << "{"
        << "\"device_count\": " << supervisor.devices.size() << ", "
        << "\"retry_policy\": {"
        << "\"max_attempts\": " << supervisor.retry_policy.max_attempts << ", "
        << "\"base_delay_ms\": " << supervisor.retry_policy.base_delay_ms << ", "
        << "\"max_delay_ms\": " << supervisor.retry_policy.max_delay_ms << ", "
        << "\"backoff_multiplier\": " << supervisor.retry_policy.backoff_multiplier
        << "}, "
        << "\"devices\": [";

    for (std::size_t index = 0; index < supervisor.devices.size(); ++index) {
        const DeviceRuntime& device = supervisor.devices[index];
        out << "{"
            << "\"device_id\": " << quote(device.device_id) << ", "
            << "\"board\": " << quote(device.profile.name) << ", "
            << "\"lifecycle\": " << quote(lifecycle_state_name(device.lifecycle)) << ", "
            << "\"outbound_buffer_depth\": " << device.outbound_buffer.frames.size() << ", "
            << "\"inbound_buffer_depth\": " << device.inbound_buffer.frames.size() << ", "
            << "\"protocol_sessions\": " << device.protocol_sessions.size() << ", "
            << "\"network_sessions\": " << device.network_sessions.size()
            << "}";
        out << (index + 1 == supervisor.devices.size() ? "" : ", ");
    }
    out << "]}";
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
