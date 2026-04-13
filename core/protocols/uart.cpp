#include "../config.h"

namespace iotron {

ProtocolProfile uart_profile() {
    return ProtocolProfile{"uart", "embedded-bus", "serial", true, 1024, {"console", "modem", "debug"}};
}

}  // namespace iotron
