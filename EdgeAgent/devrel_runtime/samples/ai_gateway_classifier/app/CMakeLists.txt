cmake_minimum_required(VERSION 3.14)
project(mobilenetv2 C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# ── gwapps SDK ──
# Resolves headers and per-arch libraries from DevRel's vendored gwapps SDK.
# Set GWAPPS_SDK_ROOT explicitly, or rely on the default below.
set(GWAPPS_SDK_ROOT "/Users/pavanr/work/DevRel/DevRel/sdks/gwapps/0.0.0-dev-20260520" CACHE PATH "gwapps SDK root")

if(NOT EXISTS "${GWAPPS_SDK_ROOT}/include")
    message(FATAL_ERROR "GWAPPS_SDK_ROOT='${GWAPPS_SDK_ROOT}' does not contain include/")
endif()

# ── Target arch ──
# Default matches the version we cut codegen against; override with
# -DGWAPPS_TARGET_ARCH=<arch> to retarget the same source.
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

find_library(GWAPPS_NWAIOS_LIB     NAMES nwaios               PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)
find_library(GWAPPS_TRANSPORT_LIB  NAMES GwAppstransport      PATHS ${GWAPPS_LIB_DIR} NO_DEFAULT_PATH)

if(NOT GWAPPS_NWAIOS_LIB)
    message(FATAL_ERROR "libnwaios not found under ${GWAPPS_LIB_DIR}")
endif()

# ── App ──
add_executable(mobilenetv2
    src/main.c
    src/tensor_io.c
)

target_link_libraries(mobilenetv2
    PRIVATE
        ${GWAPPS_NWAIOS_LIB}
        ${GWAPPS_TRANSPORT_LIB}
        pthread
        dl
)

install(TARGETS mobilenetv2 RUNTIME DESTINATION usr/bin)
install(FILES config/service.json DESTINATION etc/mobilenetv2)
