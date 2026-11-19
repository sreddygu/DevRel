cmake_minimum_required(VERSION 3.10)
project(ad_lib C)

# Set C standard
set(CMAKE_C_STANDARD 99)

# Define paths
set(SRCPATH ${CMAKE_SOURCE_DIR})
set(INCLUDEPATH ${CMAKE_SOURCE_DIR}/include)
set(GWAPPS_INSTALL_DIR "${CMAKE_SOURCE_DIR}/../../ad_libs_bins" CACHE PATH "Installation directory for ad library")

# Find all source files
file(GLOB SOURCES ${SRCPATH}/*.c)

# Create the shared library
add_library(${PROJECT_NAME} SHARED ${SOURCES})

# Include directories (target-specific)
target_include_directories(${PROJECT_NAME} PRIVATE
    ${INCLUDEPATH}
    ${SRCPATH}/../src
    ${GWAPPS_FRAMEWORK_LIBS_BIN_DIR}
    ${SRCPATH}/../../../frmwrk/gwapps_cmn_headers/transport_lib
    ${SRCPATH}/../../../frmwrk/gwapps_cmn_headers/telemetry_service_app
    ${SRCPATH}/../../../frmwrk/gwapps_cmn_headers/ad
)

# Compiler options (target-specific)
target_compile_options(${PROJECT_NAME} PRIVATE
    -Wall
    -UENABLE_DEBUG
    -rdynamic
    -g3
    -fvisibility=default
    -O0
    -fstack-protector-strong
)

# Linker options and libraries
target_link_options(${PROJECT_NAME} PRIVATE -Wl,--no-whole-archive)
target_link_directories(${PROJECT_NAME} PRIVATE ${GWAPPS_FRAMEWORK_LIBS_BIN_DIR})
target_link_libraries(${PROJECT_NAME} PRIVATE dl GwAppstransport)

# Post-build: copy the shared library to install directory
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:${PROJECT_NAME}>
            ${GWAPPS_INSTALL_DIR}/$<TARGET_FILE_NAME:${PROJECT_NAME}>
    COMMENT "Copying ad_lib binary to ${GWAPPS_INSTALL_DIR}"
)

# Optional: install target
install(TARGETS ${PROJECT_NAME} DESTINATION ${GWAPPS_INSTALL_DIR})

