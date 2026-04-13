#include "../config.h"

namespace iotron {

NetworkTransport grpc_transport() {
    return NetworkTransport{"grpc", "http2", 50051, true, {"rpc", "streaming", "service-mesh"}};
}

}  // namespace iotron
