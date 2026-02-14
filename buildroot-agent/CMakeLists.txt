cmake_minimum_required(VERSION 2.8.12)

# 设置CMP0048策略为旧行为，避免PROJECT_VERSION警告
cmake_policy(SET CMP0048 OLD)

project(buildroot-agent C)

# 允许命令行覆盖：cmake -DAGENT_VERSION=1.2.0 ...
if(DEFINED AGENT_VERSION)
    set(PROJECT_VERSION "${AGENT_VERSION}" CACHE STRING "Agent version" FORCE)
    message(STATUS "Version overridden by AGENT_VERSION: ${PROJECT_VERSION}")
# 读取 VERSION.txt 作为默认版本号
elseif(EXISTS "${CMAKE_SOURCE_DIR}/VERSION.txt")
    file(READ "${CMAKE_SOURCE_DIR}/VERSION.txt" VERSION_FILE_CONTENT)
    string(STRIP "${VERSION_FILE_CONTENT}" VERSION_FROM_FILE)
    set(PROJECT_VERSION "${VERSION_FROM_FILE}" CACHE STRING "Agent version")
    message(STATUS "Using version from VERSION.txt: ${PROJECT_VERSION}")
else()
    set(PROJECT_VERSION "1.0.0" CACHE STRING "Agent version")
    message(STATUS "VERSION.txt not found, using default version: ${PROJECT_VERSION}")
endif()

# 生成 version.h 头文件
configure_file(
    "${CMAKE_SOURCE_DIR}/version.h.in"
    "${CMAKE_BINARY_DIR}/version.h"
)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin)

# 接受架构参数
if(DEFINED ARCH)
    message(STATUS "Building for architecture: ${ARCH}")
else()
    set(ARCH "x86_64")
    message(STATUS "Architecture not specified, using default: ${ARCH}")
endif()

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -D_GNU_SOURCE -std=gnu99")

# 将生成的头文件路径添加到include目录
include_directories("${CMAKE_BINARY_DIR}")

include_directories(${PROJECT_SOURCE_DIR}/include)

# Exclude agent_http.c since we've replaced it with TCP download
file(GLOB SOURCES "${PROJECT_SOURCE_DIR}/src/*.c")
list(REMOVE_ITEM SOURCES "${PROJECT_SOURCE_DIR}/src/agent_http.c")
add_executable(${PROJECT_NAME} ${SOURCES})

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_definitions(-DDEBUG)
endif()

if(STATIC_LINK)
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static -static-libgcc")
    target_link_libraries(${PROJECT_NAME} pthread util dl)
    message(STATUS "Using static linking")
else()
    target_link_libraries(${PROJECT_NAME} 
        pthread 
        util 
        dl
    )
    message(STATUS "Using dynamic linking")
endif()

# 安装规则
# 更新包需要二进制文件在根目录
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION .
)

# Release target - strip symbols
add_custom_target(release
    COMMAND ${CMAKE_STRIP} $<TARGET_FILE:${PROJECT_NAME}>
    DEPENDS ${PROJECT_NAME}
    COMMENT "Stripping symbols from ${PROJECT_NAME}"
)

# 自定义更新包目标 - 生成不压缩的tar包（包含架构标识）
set(UPDATE_PACKAGE_NAME "buildroot-agent")
add_custom_target(update-package
    COMMAND tar cf ${CMAKE_BINARY_DIR}/${UPDATE_PACKAGE_NAME}-${PROJECT_VERSION}-${ARCH}.tar -C ${CMAKE_RUNTIME_OUTPUT_DIRECTORY} ${PROJECT_NAME}
    COMMAND ${CMAKE_COMMAND} -E echo "Update package created: ${CMAKE_BINARY_DIR}/${UPDATE_PACKAGE_NAME}-${PROJECT_VERSION}-${ARCH}.tar"
    DEPENDS ${PROJECT_NAME}
    COMMENT "Creating update package: ${UPDATE_PACKAGE_NAME}-${PROJECT_VERSION}-${ARCH}.tar"
    VERBATIM
)

# 打包规则 - 用于CPack（可选，生成标准打包）
set(CPACK_PACKAGE_NAME "buildroot-agent")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Buildroot Agent - TCP download version")

include(CPack)