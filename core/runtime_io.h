#ifndef IOTRON_RUNTIME_IO_H
#define IOTRON_RUNTIME_IO_H

#include "config.h"

#include <cstdint>
#include <string>
#include <vector>

namespace iotron {

struct HardwareFrame {
    std::vector<std::uint8_t> bytes;
    std::string timestamp;
};

struct DriverResult {
    bool ok;
    std::string message;
    std::vector<std::uint8_t> data;
    int retry_after_ms;
};

struct DeviceDriver {
    DeviceProfile profile;
    bool initialized;
    std::string firmware_version;
    std::vector<std::string> attached_protocols;
    std::vector<std::string> diagnostics;
};

struct ProtocolDriver {
    ProtocolProfile profile;
    bool connected;
    std::uint64_t tx_count;
    std::uint64_t rx_count;
    std::vector<HardwareFrame> history;
};

struct NetworkClient {
    NetworkTransport transport;
    bool connected;
    std::string endpoint;
    std::uint64_t tx_count;
    std::uint64_t rx_count;
    int reconnect_attempts;
};

DeviceDriver create_device_driver(const DeviceProfile& profile);
ProtocolDriver create_protocol_driver(const ProtocolProfile& profile);
NetworkClient create_network_client(const NetworkTransport& transport, const std::string& endpoint);
NetworkClient create_websocket_client(const std::string& endpoint);
NetworkClient create_http_client(const std::string& endpoint);
NetworkClient create_coap_client(const std::string& endpoint);
ProtocolDriver create_i2c_driver();
DeviceDriver create_esp32_driver();

DriverResult initialize_device(DeviceDriver& driver);
DriverResult attach_protocol(DeviceDriver& driver, ProtocolDriver& protocol);
DriverResult device_write(DeviceDriver& driver, const std::string& channel, const std::vector<std::uint8_t>& payload);
DriverResult device_read(DeviceDriver& driver, const std::string& channel, std::size_t length);

DriverResult protocol_send(ProtocolDriver& driver, const std::vector<std::uint8_t>& payload, const std::string& timestamp);
DriverResult protocol_receive(ProtocolDriver& driver, std::size_t expected_length, const std::string& timestamp);
DriverResult protocol_retry(ProtocolDriver& driver, const std::string& reason);

DriverResult network_connect(NetworkClient& client);
DriverResult network_send(NetworkClient& client, const std::string& payload);
DriverResult network_receive(NetworkClient& client, const std::string& payload);
DriverResult network_schedule_reconnect(NetworkClient& client, const RetryPolicy& retry_policy, const std::string& reason);

}  // namespace iotron

#endif
