cmake_minimum_required(VERSION 2.8.12)
project(buildroot-agent C)

set(PROJECT_VERSION "1.0.0")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -D_GNU_SOURCE -std=gnu99")
add_definitions(-DVERSION="${PROJECT_VERSION}")

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
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION bin
)

# Release target - strip symbols
add_custom_target(release
    COMMAND ${CMAKE_STRIP} $<TARGET_FILE:${PROJECT_NAME}>
    DEPENDS ${PROJECT_NAME}
    COMMENT "Stripping symbols from ${PROJECT_NAME}"
)

# 打包规则
set(CPACK_PACKAGE_NAME "buildroot-agent")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Buildroot Agent - TCP download version")
set(CPACK_GENERATOR "TGZ")

include(CPack)