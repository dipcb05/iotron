#include "../../config.h"

namespace iotron {

DeviceProfile arduino_mega_profile() {
    return DeviceProfile{"arduino", "mega", "avr", "arduino-cli", "serial", false, {"gpio", "uart", "i2c", "spi", "multi-serial"}};
}

}  // namespace iotron
