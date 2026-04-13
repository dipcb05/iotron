#include "../../core/c_api.h"

extern "C" {

const char* iotron_go_manifest_json() {
    return iotron_manifest_json();
}

void iotron_go_free_string(const char* value) {
    iotron_free_string(value);
}

}
