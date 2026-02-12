#!/bin/sh
cd "$(dirname "$0")/.."
mkdir -p build
#cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
