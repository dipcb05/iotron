#include "../../config.h"

namespace iotron {

DeviceProfile jetson_orin_profile() {
    return DeviceProfile{"jetson", "orin", "arm64", "jetpack", "ssh", true, {"gpu", "camera", "docker", "python", "cuda", "tensorrt"}};
}

}  // namespace iotron
