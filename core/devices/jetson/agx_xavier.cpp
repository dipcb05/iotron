#include "../../config.h"

namespace iotron {

DeviceProfile jetson_agx_xavier_profile() {
    return DeviceProfile{"jetson", "agx-xavier", "arm64", "jetpack", "ssh", true, {"gpu", "camera", "docker", "python", "cuda", "edge-ai"}};
}

}  // namespace iotron
