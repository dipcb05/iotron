#include "../../config.h"

namespace iotron {

DeviceProfile teensy4_profile() {
    return DeviceProfile{"teensy", "teensy4", "arm", "teensy-loader", "usb", false, {"uart", "i2c", "spi", "can", "high-speed-dsp"}};
}

}  // namespace iotron
