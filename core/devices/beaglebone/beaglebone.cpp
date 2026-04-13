#include "../../config.h"

namespace iotron {

DeviceProfile beaglebone_black_profile() {
    return DeviceProfile{"beaglebone", "beaglebone-black", "arm", "apt-ssh", "ssh", true, {"linux", "gpio", "pru", "uart", "i2c", "spi"}};
}

}  // namespace iotron
