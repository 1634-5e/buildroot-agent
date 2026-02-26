cmake_minimum_required(VERSION 2.8.12)
project(buildroot-agent C)

# 从 VERSION 文件读取版本号
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" PROJECT_VERSION)
string(STRIP "${PROJECT_VERSION}" PROJECT_VERSION)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin)

# 获取构建信息
string(TIMESTAMP BUILD_DATE "%Y-%m-%d %H:%M:%S" UTC)
find_package(Git QUIET)
if(GIT_FOUND)
    execute_process(
        COMMAND ${GIT_EXECUTABLE} rev-parse --short HEAD
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        OUTPUT_VARIABLE GIT_COMMIT
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
else()
    set(GIT_COMMIT "unknown")
endif()

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -D_GNU_SOURCE -std=gnu99")
add_definitions(-DAGENT_VERSION="${PROJECT_VERSION}")

include_directories(${PROJECT_SOURCE_DIR}/include ${PROJECT_SOURCE_DIR}/third_party/libconfig/lib)

add_subdirectory(third_party/libconfig)
# Exclude agent_http.c and agent_yaml.c (replaced by agent_config_file.c)
file(GLOB SOURCES "${PROJECT_SOURCE_DIR}/src/*.c")
list(REMOVE_ITEM SOURCES "${PROJECT_SOURCE_DIR}/src/agent_http.c" "${PROJECT_SOURCE_DIR}/src/agent_yaml.c")
add_executable(${PROJECT_NAME} ${SOURCES})

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_definitions(-DDEBUG)
endif()

if(STATIC_LINK)
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static -static-libgcc")
    target_link_libraries(${PROJECT_NAME} pthread util dl config)
    message(STATUS "Using static linking")
else()
    target_link_libraries(${PROJECT_NAME} 
        pthread 
        util 
        dl
        config
    )
    message(STATUS "Using dynamic linking")
endif()

# 安装规则 - 单目录自包含
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION .
)

# 安装配置文件示例
install(FILES agent.cfg
    DESTINATION .
)

# 安装文档
install(DIRECTORY doc/
    DESTINATION doc
    FILES_MATCHING PATTERN "*.md" PATTERN "LICENSE" PATTERN "MANIFEST"
)

# 生成 MANIFEST 文件
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/doc/MANIFEST.in
    ${CMAKE_CURRENT_BINARY_DIR}/MANIFEST
    @ONLY
)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/MANIFEST
    DESTINATION doc
)

# Release target - strip symbols
add_custom_target(release
    COMMAND ${CMAKE_STRIP} $<TARGET_FILE:${PROJECT_NAME}>
    DEPENDS ${PROJECT_NAME}
    COMMENT "Stripping symbols from ${PROJECT_NAME}"
)

# Generate config example (auto-regenerate when agent.h changes)
# Skip for cross-compiling since ARM binary cannot run on host
if(NOT CMAKE_CROSSCOMPILING)
    add_custom_command(
        OUTPUT ${CMAKE_SOURCE_DIR}/agent.cfg
        COMMAND $<TARGET_FILE:${PROJECT_NAME}> -g -e -c ${CMAKE_SOURCE_DIR}/agent.cfg
        DEPENDS ${PROJECT_NAME} ${CMAKE_SOURCE_DIR}/include/agent.h
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        COMMENT "Generating agent.cfg"
    )

    add_custom_target(config-example ALL
        DEPENDS ${CMAKE_SOURCE_DIR}/agent.cfg
    )
endif()

# 打包规则 - 使用 TAR（不压缩）
set(CPACK_PACKAGE_NAME "buildroot-agent")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Buildroot Agent - 嵌入式设备远程管理Agent")
set(CPACK_PACKAGE_VENDOR "Buildroot Agent Team")
set(CPACK_PACKAGE_CONTACT "support@buildroot-agent.com")
set(CPACK_GENERATOR "TAR")
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY 1)

include(CPack)