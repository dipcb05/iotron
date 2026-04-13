#include "../../config.h"
#include "../../runtime_io.h"

namespace iotron {

DeviceProfile esp32_profile() {
    return DeviceProfile{"espressif", "esp32", "xtensa", "esptool", "uart", true, {"wifi", "bluetooth", "uart", "i2c", "spi", "can"}};
}

DeviceDriver create_esp32_edge_driver() {
    return create_esp32_driver();
}

DriverResult esp32_boot(DeviceDriver& driver) {
    return initialize_device(driver);
}

DriverResult esp32_probe_firmware(DeviceDriver& driver) {
    if (!driver.initialized) {
        return DriverResult{false, "esp32 not initialized", {}, 250};
    }
    std::vector<std::uint8_t> version(driver.firmware_version.begin(), driver.firmware_version.end());
    return DriverResult{true, "firmware probe ok", version, 0};
}

}  // namespace iotron
