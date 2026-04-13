#include "../config.h"
#include "../runtime_io.h"

namespace iotron {

NetworkTransport websocket_transport() {
    return NetworkTransport{"websocket", "ws", 8080, false, {"bi-directional", "realtime", "dashboard-stream"}};
}

NetworkClient create_dashboard_websocket(const std::string& endpoint) {
    return create_websocket_client(endpoint);
}

DriverResult websocket_publish(NetworkClient& client, const std::string& json_payload) {
    if (!client.connected) {
        DriverResult connect_result = network_connect(client);
        if (!connect_result.ok) {
            return connect_result;
        }
    }
    return network_send(client, json_payload);
}

DriverResult websocket_consume(NetworkClient& client, const std::string& json_payload) {
    if (!client.connected) {
        return network_schedule_reconnect(client, default_retry_policy(), "websocket disconnected");
    }
    return network_receive(client, json_payload);
}

}  // namespace iotron
