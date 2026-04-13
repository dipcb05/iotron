#include "../config.h"

namespace iotron {

NetworkTransport mqtt_transport() {
    return NetworkTransport{"mqtt", "tcp", 1883, false, {"pubsub", "telemetry", "retained-messages"}};
}

}  // namespace iotron
