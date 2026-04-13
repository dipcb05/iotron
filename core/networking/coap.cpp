#include "../config.h"
#include "../runtime_io.h"

namespace iotron {

NetworkTransport coap_transport() {
    return NetworkTransport{"coap", "udp", 5683, false, {"constrained-device", "low-bandwidth", "observe"}};
}

NetworkClient create_coap_observer(const std::string& endpoint) {
    return create_coap_client(endpoint);
}

DriverResult coap_observe(NetworkClient& client, const std::string& resource) {
    if (!client.connected) {
        DriverResult connect_result = network_connect(client);
        if (!connect_result.ok) {
            return connect_result;
        }
    }
    return network_send(client, "OBSERVE " + resource);
}

DriverResult coap_notification(NetworkClient& client, const std::string& payload) {
    if (!client.connected) {
        return network_schedule_reconnect(client, default_retry_policy(), "coap observer disconnected");
    }
    return network_receive(client, payload);
}

}  // namespace iotron
