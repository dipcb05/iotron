#include "../config.h"

namespace iotron {

ProtocolProfile can_profile() {
    return ProtocolProfile{"can", "industrial", "field-bus", true, 64, {"deterministic", "multi-node", "fault-tolerant"}};
}

}  // namespace iotron
