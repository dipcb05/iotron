#include "../../config.h"

namespace iotron {

DeviceProfile esp32s3_profile() {
    return DeviceProfile{"espressif", "esp32s3", "xtensa", "esptool", "uart", true, {"wifi", "bluetooth-le", "vector-acceleration", "uart", "i2c", "spi"}};
}

}  // namespace iotron
