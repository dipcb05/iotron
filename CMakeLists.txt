cmake_minimum_required(VERSION 3.16)
project(iotron_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(IOTRON_CORE_SOURCES
    core/core.cpp
    core/c_api.cpp
    core/runtime_io.cpp
    core/storage/sqlite_handler.cpp
    core/protocols/i2c.cpp
    core/protocols/spi.cpp
    core/protocols/uart.cpp
    core/protocols/can.cpp
    core/protocols/modbus.cpp
    core/networking/mqtt.cpp
    core/networking/http.cpp
    core/networking/websocket.cpp
    core/networking/coap.cpp
    core/networking/grpc.cpp
    core/devices/arduino/uno.cpp
    core/devices/arduino/nano.cpp
    core/devices/arduino/mega.cpp
    core/devices/arduino/due.cpp
    core/devices/arduino/mkr1000.cpp
    core/devices/espressif/esp8266.cpp
    core/devices/espressif/esp32.cpp
    core/devices/espressif/esp32c3.cpp
    core/devices/espressif/esp32s2.cpp
    core/devices/espressif/esp32s3.cpp
    core/devices/jetson/nano.cpp
    core/devices/jetson/tx2.cpp
    core/devices/jetson/orin.cpp
    core/devices/jetson/agx_xavier.cpp
    core/devices/teensy/teensy_lc.cpp
    core/devices/teensy/teensy3.cpp
    core/devices/teensy/teensy4.cpp
    core/devices/stm32/stm32.cpp
    core/devices/raspberrypi/pi3.cpp
    core/devices/beaglebone/beaglebone.cpp
)

add_library(iotron_native SHARED ${IOTRON_CORE_SOURCES})
target_include_directories(iotron_native PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/core)

if(MSVC)
    target_compile_options(iotron_native PRIVATE /W4)
else()
    target_compile_options(iotron_native PRIVATE -Wall -Wextra -Wpedantic)
endif()
