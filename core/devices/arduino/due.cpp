#include "../../config.h"

namespace iotron {

DeviceProfile arduino_due_profile() {
    return DeviceProfile{"arduino", "due", "arm", "arduino-cli", "serial", false, {"gpio", "uart", "i2c", "spi", "can"}};
}

}  // namespace iotron
