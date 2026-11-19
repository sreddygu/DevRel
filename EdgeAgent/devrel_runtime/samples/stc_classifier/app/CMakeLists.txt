cmake_minimum_required(VERSION 3.14)
project(stc_classifier C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Production hardening flags — match the gwapps reference apps.
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -O2 -fstack-protector-strong -rdynamic -g3")

# ── gwapps SDK ──
set(GWAPPS_SDK_ROOT "C:\work\DevRel\DevRel\sdks\gwapps\1.0.0-from-source-20260521" CACHE PATH "gwapps SDK root")

if(NOT EXISTS "${GWAPPS_SDK_ROOT}/include")
    message(FATAL_ERROR "GWAPPS_SDK_ROOT='${GWAPPS_SDK_ROOT}' does not contain include/")
endif()

# ── Target arch ──
set(GWAPPS_TARGET_ARCH "aarch64-openwrt-linux" CACHE STRING "Cross-compile target arch")
set(GWAPPS_LIB_DIR "${GWAPPS_SDK_ROOT}/lib/${GWAPPS_TARGET_ARCH}")
if(NOT IS_DIRECTORY "${GWAPPS_LIB_DIR}")
    message(FATAL_ERROR "No libs at ${GWAPPS_LIB_DIR} — check GWAPPS_TARGET_ARCH")
endif()

message(STATUS "gwapps SDK   : ${GWAPPS_SDK_ROOT}")
message(STATUS "Target arch  : ${GWAPPS_TARGET_ARCH}")
message(STATUS "Libs dir     : ${GWAPPS_LIB_DIR}")

# ── Headers + libraries ──
include_directories(${GWAPPS_SDK_ROOT}/include)

find_library(GWAPPS_NWAIOS_LIB         NAMES nwaios               PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)
find_library(GWAPPS_TRANSPORT_LIB      NAMES GwAppstransport      PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)
find_library(GWAPPS_LICENSE_LIB        NAMES gwapps_license_lib   PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)
find_library(GWAPPS_WLANIF_LIB         NAMES gwapps_wlanif_lib    PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)
find_library(GWAPPS_UTILS_LIB          NAMES gwapps_utils_lib     PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)
find_library(GWAPPS_CIA_LIB            NAMES gwapps_cia gwapps_cia_lib  PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)

if(NOT GWAPPS_NWAIOS_LIB)
    message(FATAL_ERROR "libnwaios not found under ${GWAPPS_LIB_DIR}")
endif()

# Optional: json-c (the production reference apps link it for config parsing)
find_library(JSON_C_LIB NAMES json-c)

# ── App ──
# Modular layout — one .c per architectural concern, mirroring the
# production reference (see samples/gwapps_fault_detection/README.md).
# The three architectural concerns each have their own module:
#   feature extraction → tensor_io.c
#   inferencing        → model_inferencing.c
#   turnkey            → turnkey.c
# plus debugging.c (logging primitives) used by all three.
add_executable(stc_classifier
    src/main.c
    src/model_inferencing.c
    src/tensor_io.c
    src/turnkey.c
    src/debugging.c
    src/cloud_services.c
)

target_link_libraries(stc_classifier
    PRIVATE
        ${GWAPPS_NWAIOS_LIB}
        ${GWAPPS_TRANSPORT_LIB}
        $<$<BOOL:${GWAPPS_LICENSE_LIB}>:${GWAPPS_LICENSE_LIB}>
        $<$<BOOL:${GWAPPS_WLANIF_LIB}>:${GWAPPS_WLANIF_LIB}>
        $<$<BOOL:${GWAPPS_UTILS_LIB}>:${GWAPPS_UTILS_LIB}>
        $<$<BOOL:${GWAPPS_CIA_LIB}>:${GWAPPS_CIA_LIB}>
        $<$<BOOL:${JSON_C_LIB}>:${JSON_C_LIB}>
        pthread
        dl
)

install(TARGETS stc_classifier RUNTIME DESTINATION usr/bin)
install(FILES config/service.json DESTINATION etc/stc_classifier)
install(FILES config/oci_config.json DESTINATION etc/stc_classifier RENAME config.json)
