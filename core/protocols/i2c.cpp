#include "../config.h"
#include "../runtime_io.h"

namespace iotron {

ProtocolProfile i2c_profile() {
    return ProtocolProfile{"i2c", "embedded-bus", "two-wire", false, 255, {"addressed", "sensor-bus", "short-range"}};
}

ProtocolDriver create_sensor_i2c_bus() {
    return create_i2c_driver();
}

DriverResult i2c_write_register(ProtocolDriver& driver, std::uint8_t address, std::uint8_t reg, std::uint8_t value, const std::string& timestamp) {
    std::vector<std::uint8_t> frame = {address, reg, value};
    return protocol_send(driver, frame, timestamp);
}

DriverResult i2c_read_register(ProtocolDriver& driver, std::uint8_t address, std::uint8_t reg, const std::string& timestamp) {
    std::vector<std::uint8_t> request = {address, reg};
    DriverResult sent = protocol_send(driver, request, timestamp);
    if (!sent.ok) {
        return sent;
    }
    return protocol_receive(driver, 1, timestamp);
}

}  // namespace iotron
