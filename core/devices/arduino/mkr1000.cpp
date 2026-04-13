#include "../../config.h"

namespace iotron {

DeviceProfile arduino_mkr1000_profile() {
    return DeviceProfile{"arduino", "mkr1000", "samd21", "arduino-cli", "serial", true, {"wifi", "gpio", "uart", "i2c", "spi"}};
}

}  // namespace iotron
