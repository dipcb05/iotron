#include "../../config.h"

namespace iotron {

DeviceProfile jetson_tx2_profile() {
    return DeviceProfile{"jetson", "tx2", "arm64", "jetpack", "ssh", true, {"gpu", "camera", "docker", "python", "cuda"}};
}

}  // namespace iotron
