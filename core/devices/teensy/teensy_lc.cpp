#include "../../config.h"

namespace iotron {

DeviceProfile teensy_lc_profile() {
    return DeviceProfile{"teensy", "teensy-lc", "arm", "teensy-loader", "usb", false, {"uart", "i2c", "spi", "low-power"}};
}

}  // namespace iotron
