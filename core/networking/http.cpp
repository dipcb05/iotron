#include "../config.h"

namespace iotron {

NetworkTransport http_transport() {
    return NetworkTransport{"http", "http", 80, false, {"rest", "webhooks", "management-api"}};
}

}  // namespace iotron
