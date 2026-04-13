#include "../config.h"

namespace iotron {

ProtocolProfile i2c_profile() {
    return ProtocolProfile{"i2c", "embedded-bus", "two-wire", false, 255, {"addressed", "sensor-bus", "short-range"}};
}

}  // namespace iotron
