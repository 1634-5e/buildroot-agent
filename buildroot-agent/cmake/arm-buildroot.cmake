set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(TOOLCHAIN_PATH "/workspaces/buildroot-agent/package/buildroot/output/host/usr")
set(SYSROOT_PATH "/workspaces/buildroot-agent/package/armhf-sysroot")

set(CMAKE_C_COMPILER "${TOOLCHAIN_PATH}/bin/arm-buildroot-linux-uclibcgnueabi-gcc")
set(CMAKE_CXX_COMPILER "${TOOLCHAIN_PATH}/bin/arm-buildroot-linux-uclibcgnueabi-g++")
set(CMAKE_STRIP "${TOOLCHAIN_PATH}/bin/arm-buildroot-linux-uclibcgnueabi-strip")

set(CMAKE_FIND_ROOT_PATH "${SYSROOT_PATH}" "${TOOLCHAIN_PATH}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

set(CMAKE_SYSROOT "${SYSROOT_PATH}")

set(ENV{PKG_CONFIG_PATH} "${SYSROOT_PATH}/usr/lib/pkgconfig")
set(ENV{PKG_CONFIG_LIBDIR} "${SYSROOT_PATH}/usr/lib/pkgconfig")
