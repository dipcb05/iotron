#include "../../config.h"

namespace iotron {

DeviceProfile esp32_profile() {
    return DeviceProfile{"espressif", "esp32", "xtensa", "esptool", "uart", true, {"wifi", "bluetooth", "uart", "i2c", "spi", "can"}};
}

}  // namespace iotron
