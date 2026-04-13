#include "../config.h"

namespace iotron {

NetworkTransport coap_transport() {
    return NetworkTransport{"coap", "udp", 5683, false, {"constrained-device", "low-bandwidth", "observe"}};
}

}  // namespace iotron
