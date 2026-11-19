#
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.
#

cmake_minimum_required(VERSION 3.10)
project(ad C)

# Set C standard
set(CMAKE_C_STANDARD 99)

# Set output directories
set(SRCPATH ${CMAKE_SOURCE_DIR})
set(OBJPATH ${CMAKE_BINARY_DIR}/obj)

# Set compiler flags
#set(EXTRA_CFLAGS "-Wall -Werror -UENABLE_DEBUG -O2 -rdynamic -g3")
set(EXTRA_CFLAGS "-Wall  -UENABLE_DEBUG -O2 -rdynamic -g3 -fstack-protector-strong")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${EXTRA_CFLAGS}")

# Include directories
include_directories(
    ${INCLUDEPATH}
    ../src
    ${GWAPPS_FRAMEWORK_LIBS_BIN_DIR}
    ../../../frmwrk/gwapps_cmn_headers/transport_lib
    ../../../frmwrk/gwapps_cmn_headers/nwaios
    ../../../frmwrk/gwapps_cmn_headers/license_lib
)

# Find all source files
file(GLOB SOURCES ${SRCPATH}/*.c)

# Create the executable
add_executable(${PROJECT_NAME} ${SOURCES})

target_link_directories(${PROJECT_NAME} PRIVATE ${GWAPPS_FRAMEWORK_LIBS_BIN_DIR})

# Link libraries
target_link_libraries(${PROJECT_NAME} PRIVATE dl GwAppstransport nwaios gwapps_license_lib json-c)

set(GWAPPS_INSTALL_DIR "${CMAKE_SOURCE_DIR}/../../ad_libs_bins" CACHE PATH "Installation directory for ad app")
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:${PROJECT_NAME}>
            ${GWAPPS_INSTALL_DIR}/$<TARGET_FILE_NAME:${PROJECT_NAME}>
    COMMENT "Copying ad_app binary to ${GWAPPS_INSTALL_DIR}"
)
if (0)
add_custom_target(build_containers ALL
    COMMAND ${CMAKE_COMMAND} -E echo "Running build_containers.sh..."
    COMMAND ${CMAKE_COMMAND} -E env bash ${CMAKE_SOURCE_DIR}/build_containers.sh --output ./build ${PROJECT_NAME}
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Building containers using build_containers.sh"
)

add_dependencies(build_containers ${PROJECT_NAME})

# Custom command to copy the output tar files after build_containers
add_custom_command(TARGET build_containers POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${CMAKE_SOURCE_DIR}/build/${PROJECT_NAME}-docker-image.tar
            ${GWAPPS_INSTALL_DIR}/${PROJECT_NAME}-docker-image.tar
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${CMAKE_SOURCE_DIR}/build/${PROJECT_NAME}-runc.tar.gz
            ${GWAPPS_INSTALL_DIR}/${PROJECT_NAME}-runc.tar.gz
    COMMENT "Copying container bundle outputs to install directory"
)
endif()
