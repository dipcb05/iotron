#include "../../config.h"

namespace iotron {

DeviceProfile stm32_profile() {
    return DeviceProfile{"stm32", "stm32", "arm", "stm32-programmer", "swd", true, {"uart", "i2c", "spi", "can", "low-level-hal"}};
}

}  // namespace iotron
