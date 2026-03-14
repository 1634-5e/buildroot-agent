cmake_minimum_required(VERSION 2.8.12)
cmake_policy(SET CMP0048 NEW)
set(LIBCONFIG_VERSION_MAJOR 1)
set(LIBCONFIG_VERSION_MINOR 7)
set(LIBCONFIG_VERSION_PATCH 2)
set(LIBCONFIG_VERSION "${LIBCONFIG_VERSION_MAJOR}.${LIBCONFIG_VERSION_MINOR}.${LIBCONFIG_VERSION_PATCH}")
project(libconfig VERSION ${LIBCONFIG_VERSION} LANGUAGES C)
option(BUILD_SHARED_LIBS "Build shared library" OFF)
option(BUILD_CXX "Build C++ library" OFF)

set(libsrc
    lib/grammar.c
    lib/libconfig.c
    lib/scanctx.c
    lib/scanner.c
    lib/strbuf.c
    lib/strvec.c
    lib/util.c
    lib/wincompat.c
)

if(MSVC)
    set(libname "libconfig")
else()
    set(libname "config")
endif()

add_library(${libname} ${libsrc})
target_include_directories(${libname} PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 确保包含系统头文件路径
include_directories(/usr/include)

if(NOT BUILD_SHARED_LIBS)
    target_compile_definitions(${libname} PUBLIC LIBCONFIG_STATIC)
endif()

# Check for locale functions
include(CheckSymbolExists)
check_symbol_exists(uselocale "locale.h" HAVE_USELOCALE)
check_symbol_exists(newlocale "locale.h" HAVE_NEWLOCALE)
check_symbol_exists(freelocale "locale.h" HAVE_FREELOCALE)

if(HAVE_USELOCALE)
    target_compile_definitions(${libname} PRIVATE HAVE_USELOCALE)
endif()
if(HAVE_NEWLOCALE)
    target_compile_definitions(${libname} PRIVATE HAVE_NEWLOCALE)
endif()
if(HAVE_FREELOCALE)
    target_compile_definitions(${libname} PRIVATE HAVE_FREELOCALE)
endif()

if(MSVC)
    target_compile_definitions(${libname} PRIVATE
        _CRT_SECURE_NO_DEPRECATE
        YY_NO_UNISTD_H
        YY_USE_CONST
    )
endif()

if(WIN32)
    target_link_libraries(${libname} shlwapi)
endif()