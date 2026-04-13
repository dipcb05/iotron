#include "../../config.h"

namespace iotron {

DeviceProfile arduino_nano_profile() {
    return DeviceProfile{"arduino", "nano", "avr", "arduino-cli", "serial", false, {"gpio", "uart", "i2c", "spi", "low-power"}};
}

}  // namespace iotron
