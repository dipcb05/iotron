#include "runtime_io.h"

#include <algorithm>
#include <sstream>

namespace iotron {
namespace {

std::vector<std::uint8_t> padded_data(const std::string& source, std::size_t length) {
    std::vector<std::uint8_t> result(source.begin(), source.end());
    result.resize(length, 0);
    return result;
}

}  // namespace

DeviceDriver create_device_driver(const DeviceProfile& profile) {
    return DeviceDriver{profile, false, "unknown", {}, {}};
}

ProtocolDriver create_protocol_driver(const ProtocolProfile& profile) {
    return ProtocolDriver{profile, false, 0, 0, {}};
}

NetworkClient create_network_client(const NetworkTransport& transport, const std::string& endpoint) {
    return NetworkClient{transport, false, endpoint, 0, 0, 0};
}

NetworkClient create_websocket_client(const std::string& endpoint) {
    return create_network_client(websocket_transport(), endpoint);
}

NetworkClient create_http_client(const std::string& endpoint) {
    return create_network_client(http_transport(), endpoint);
}

NetworkClient create_coap_client(const std::string& endpoint) {
    return create_network_client(coap_transport(), endpoint);
}

ProtocolDriver create_i2c_driver() {
    return create_protocol_driver(i2c_profile());
}

DeviceDriver create_esp32_driver() {
    return create_device_driver(esp32_profile());
}

DriverResult initialize_device(DeviceDriver& driver) {
    driver.initialized = true;
    driver.firmware_version = "runtime-0.3.0";
    driver.diagnostics.push_back("device-initialized");
    return DriverResult{true, "device initialized", {}, 0};
}

DriverResult attach_protocol(DeviceDriver& driver, ProtocolDriver& protocol) {
    if (!driver.initialized) {
        return DriverResult{false, "device must be initialized first", {}, 250};
    }
    protocol.connected = true;
    if (std::find(driver.attached_protocols.begin(), driver.attached_protocols.end(), protocol.profile.name) == driver.attached_protocols.end()) {
        driver.attached_protocols.push_back(protocol.profile.name);
    }
    return DriverResult{true, "protocol attached", {}, 0};
}

DriverResult device_write(DeviceDriver& driver, const std::string& channel, const std::vector<std::uint8_t>& payload) {
    if (!driver.initialized) {
        return DriverResult{false, "device offline", {}, 250};
    }
    std::ostringstream message;
    message << "wrote " << payload.size() << " bytes to " << channel;
    driver.diagnostics.push_back(message.str());
    return DriverResult{true, message.str(), payload, 0};
}

DriverResult device_read(DeviceDriver& driver, const std::string& channel, std::size_t length) {
    if (!driver.initialized) {
        return DriverResult{false, "device offline", {}, 250};
    }
    std::ostringstream source;
    source << driver.profile.name << ":" << channel;
    return DriverResult{true, "read completed", padded_data(source.str(), length), 0};
}

DriverResult protocol_send(ProtocolDriver& driver, const std::vector<std::uint8_t>& payload, const std::string& timestamp) {
    if (!driver.connected) {
        return DriverResult{false, "protocol disconnected", {}, 250};
    }
    driver.tx_count += 1;
    driver.history.push_back(HardwareFrame{payload, timestamp});
    return DriverResult{true, "protocol send ok", payload, 0};
}

DriverResult protocol_receive(ProtocolDriver& driver, std::size_t expected_length, const std::string& timestamp) {
    if (!driver.connected) {
        return DriverResult{false, "protocol disconnected", {}, 250};
    }
    driver.rx_count += 1;
    std::vector<std::uint8_t> payload(expected_length, static_cast<std::uint8_t>(driver.profile.name.size()));
    driver.history.push_back(HardwareFrame{payload, timestamp});
    return DriverResult{true, "protocol receive ok", payload, 0};
}

DriverResult protocol_retry(ProtocolDriver& driver, const std::string& reason) {
    driver.connected = false;
    return DriverResult{false, "retry protocol after error: " + reason, {}, 500};
}

DriverResult network_connect(NetworkClient& client) {
    client.connected = true;
    client.reconnect_attempts = 0;
    return DriverResult{true, "network connected", {}, 0};
}

DriverResult network_send(NetworkClient& client, const std::string& payload) {
    if (!client.connected) {
        return DriverResult{false, "network disconnected", {}, 250};
    }
    client.tx_count += 1;
    return DriverResult{true, "network send ok", std::vector<std::uint8_t>(payload.begin(), payload.end()), 0};
}

DriverResult network_receive(NetworkClient& client, const std::string& payload) {
    if (!client.connected) {
        return DriverResult{false, "network disconnected", {}, 250};
    }
    client.rx_count += 1;
    return DriverResult{true, "network receive ok", std::vector<std::uint8_t>(payload.begin(), payload.end()), 0};
}

DriverResult network_schedule_reconnect(NetworkClient& client, const RetryPolicy& retry_policy, const std::string& reason) {
    client.connected = false;
    client.reconnect_attempts += 1;
    int delay = retry_policy.base_delay_ms;
    for (int index = 1; index < client.reconnect_attempts; ++index) {
        delay = std::min(retry_policy.max_delay_ms, static_cast<int>(delay * retry_policy.backoff_multiplier));
    }
    return DriverResult{false, "network reconnect scheduled: " + reason, {}, delay};
}

}  // namespace iotron
