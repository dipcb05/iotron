#include "../../config.h"

namespace iotron {

DeviceProfile teensy3_profile() {
    return DeviceProfile{"teensy", "teensy3", "arm", "teensy-loader", "usb", false, {"uart", "i2c", "spi", "can"}};
}

}  // namespace iotron
