cmake_minimum_required(VERSION 3.21)

project(ace_step_qnn_runner LANGUAGES CXX)

set(QAIRT_ROOT "C:/Qualcomm/AIStack/QAIRT/2.51.40.260930" CACHE PATH
    "Root directory of the QAIRT SDK")

if(NOT EXISTS "${QAIRT_ROOT}/include/QAIRT/QairtCpp/System/QairtSystemApi.hpp")
    message(FATAL_ERROR "QAIRT C++ headers not found under QAIRT_ROOT: ${QAIRT_ROOT}")
endif()

add_executable(ace_step_qnn_runner
    src/main.cpp
    src/qnn_low_level_probe.cpp
)

target_compile_features(ace_step_qnn_runner PRIVATE cxx_std_20)
target_compile_definitions(ace_step_qnn_runner PRIVATE NOMINMAX)
target_include_directories(ace_step_qnn_runner PRIVATE
    "${QAIRT_ROOT}/include/QAIRT"
    "${QAIRT_ROOT}/include/QNN"
)

if(MSVC)
    # QAIRT 2.51 C++ headers retain mutable char* diagnostic fields.
    # The SDK's type-erased C++ wrappers also narrow container sizes internally.
    target_compile_options(ace_step_qnn_runner PRIVATE /W4 /WX /Zc:strictStrings- /wd4267)
endif()
