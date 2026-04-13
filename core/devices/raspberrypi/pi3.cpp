#include "../../config.h"

namespace iotron {

DeviceProfile raspberry_pi3_profile() {
    return DeviceProfile{"raspberrypi", "raspberry-pi-3", "arm64", "apt-ssh", "ssh", true, {"linux", "gpio", "camera", "docker", "python"}};
}

}  // namespace iotron
