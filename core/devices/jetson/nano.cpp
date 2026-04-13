#include "../../config.h"

namespace iotron {

DeviceProfile jetson_nano_profile() {
    return DeviceProfile{"jetson", "nano", "arm64", "jetpack", "ssh", true, {"gpu", "camera", "docker", "python", "cuda"}};
}

}  // namespace iotron
