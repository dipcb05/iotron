#include "../../config.h"

namespace iotron {

DeviceProfile esp32c3_profile() {
    return DeviceProfile{"espressif", "esp32c3", "risc-v", "esptool", "uart", true, {"wifi", "bluetooth-le", "uart", "i2c", "spi", "low-power"}};
}

}  // namespace iotron
