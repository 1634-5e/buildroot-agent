cmake_minimum_required(VERSION 2.8.12)
project(buildroot-agent C)

set(PROJECT_VERSION "1.0.0")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -D_GNU_SOURCE -std=gnu99")
add_definitions(-DVERSION="${PROJECT_VERSION}")

include_directories(${PROJECT_SOURCE_DIR}/include)

file(GLOB SOURCES "${PROJECT_SOURCE_DIR}/src/*.c")
add_executable(${PROJECT_NAME} ${SOURCES})
target_link_libraries(${PROJECT_NAME} pthread ssl crypto util)

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_definitions(-DDEBUG)
endif()

if(STATIC_LINK)
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static")
endif()

install(TARGETS ${PROJECT_NAME} DESTINATION usr/bin)

add_custom_target(release
    COMMAND ${CMAKE_STRIP} ${PROJECT_BINARY_DIR}/bin/${PROJECT_NAME}
    COMMENT "Stripping release binary..."
)

set(CPACK_PACKAGE_NAME ${PROJECT_NAME})
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_GENERATOR TGZ)
include(CPack)
