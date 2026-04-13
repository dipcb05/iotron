#include "../config.h"

namespace iotron {

NetworkTransport websocket_transport() {
    return NetworkTransport{"websocket", "ws", 8080, false, {"bi-directional", "realtime", "dashboard-stream"}};
}

}  // namespace iotron
