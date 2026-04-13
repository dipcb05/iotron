#include "../../config.h"

namespace iotron {

DeviceProfile arduino_uno_profile() {
    return DeviceProfile{"arduino", "uno", "avr", "arduino-cli", "serial", false, {"gpio", "uart", "i2c", "spi"}};
}

}  // namespace iotron
