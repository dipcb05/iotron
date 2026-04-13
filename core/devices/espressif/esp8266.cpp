#include "../../config.h"

namespace iotron {

DeviceProfile esp8266_profile() {
    return DeviceProfile{"espressif", "esp8266", "xtensa", "esptool", "uart", true, {"wifi", "uart", "i2c", "gpio"}};
}

}  // namespace iotron
