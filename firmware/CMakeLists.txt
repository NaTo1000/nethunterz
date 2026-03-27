cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(nethunterz_firmware VERSION 1.0.0)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Custom bootloader
set(BOOTLOADER_COMPONENT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/bootloader")
