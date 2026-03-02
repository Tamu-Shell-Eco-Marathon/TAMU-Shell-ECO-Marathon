cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(myproject_test C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

pico_sdk_init()

# =========================
# Common source collection
# =========================
set(SRC_DIR ${CMAKE_CURRENT_LIST_DIR})

# Core sources for the "easycontroller" build
set(EASYCONTROLLER_SOURCES
    ${SRC_DIR}/easycontroller_refactored.c
)

# =========================
# Refactor support
# =========================
# Grab all .c files in this directory (motor_hw.c, motor_control.c, UART.c, etc.)
file(GLOB REFACTORED_SOURCES CONFIGURE_DEPENDS
    ${SRC_DIR}/*.c
)

# Prevent compiling easycontroller_refactored.c twice (it is also matched by the GLOB)
list(REMOVE_ITEM REFACTORED_SOURCES
    ${SRC_DIR}/easycontroller_refactored.c
)

# =========================
# easycontroller (release)
# =========================
add_executable(easycontroller_refactored
    ${EASYCONTROLLER_SOURCES}
    ${REFACTORED_SOURCES}
)

target_link_libraries(easycontroller_refactored
    pico_stdlib
    hardware_pwm
    hardware_adc
)

# Headers are also in the same folder
target_include_directories(easycontroller_refactored PRIVATE
    ${SRC_DIR}
)

pico_enable_stdio_usb(easycontroller_refactored 1)     # Enable USB printf output
pico_enable_stdio_uart(easycontroller_refactored 0)    # Disable serial printf output
pico_add_extra_outputs(easycontroller_refactored)      # Create .uf2 file
