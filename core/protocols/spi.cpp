#include "../config.h"

namespace iotron {

ProtocolProfile spi_profile() {
    return ProtocolProfile{"spi", "embedded-bus", "clocked-serial", true, 4096, {"high-throughput", "full-duplex", "peripheral-bus"}};
}

}  // namespace iotron
