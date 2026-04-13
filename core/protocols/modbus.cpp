#include "../config.h"

namespace iotron {

ProtocolProfile modbus_profile() {
    return ProtocolProfile{"modbus", "industrial", "rs485-tcp", false, 256, {"plc", "register-access", "industrial-control"}};
}

}  // namespace iotron
