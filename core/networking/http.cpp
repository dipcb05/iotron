#include "../config.h"
#include "../runtime_io.h"

namespace iotron {

NetworkTransport http_transport() {
    return NetworkTransport{"http", "http", 80, false, {"rest", "webhooks", "management-api"}};
}

NetworkClient create_http_management_client(const std::string& endpoint) {
    return create_http_client(endpoint);
}

DriverResult http_post(NetworkClient& client, const std::string& body) {
    if (!client.connected) {
        DriverResult connect_result = network_connect(client);
        if (!connect_result.ok) {
            return connect_result;
        }
    }
    return network_send(client, body);
}

DriverResult http_response(NetworkClient& client, const std::string& body) {
    return network_receive(client, body);
}

}  // namespace iotron
