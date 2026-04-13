#include "../../config.h"

namespace iotron {

DeviceProfile esp32s2_profile() {
    return DeviceProfile{"espressif", "esp32s2", "xtensa", "esptool", "uart", true, {"wifi", "usb-otg", "uart", "i2c", "spi"}};
}

}  // namespace iotron
