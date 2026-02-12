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
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static")
endif()

# 移除libcurl依赖，改用TCP文件传输
message(STATUS "Building without libcurl (using TCP download)")

if(STATIC_LINK)
    # 添加基本系统库用于静态链接
    target_compile_definitions(${PROJECT_NAME} PRIVATE 
        -DSTATIC_LINK_AVAILABLE=1
    )
    
    # 静态链接时需要的基本系统库
    find_library(DL_LIB dl)
    find_library(RESOLVE_LIB resolve)
    find_library(CRYPTO_LIB crypto)
    find_library(SSL_LIB ssl)
    find_library(Z_LIB z)
    
    set(STATIC_DEPS)
    if(DL_LIB)
        list(APPEND STATIC_DEPS ${DL_LIB})
    endif()
    if(RESOLVE_LIB)
        list(APPEND STATIC_DEPS ${RESOLVE_LIB})
    endif()
    if(CRYPTO_LIB)
        list(APPEND STATIC_DEPS ${CRYPTO_LIB})
    endif()
    if(SSL_LIB)
        list(APPEND STATIC_DEPS ${SSL_LIB})
    endif()
    if(Z_LIB)
        list(APPEND STATIC_DEPS ${Z_LIB})
    endif()
    
    target_link_libraries(${PROJECT_NAME} 
        pthread 
        util 
        ${STATIC_DEPS}
    )
    message(STATUS "Using static linking without libcurl (TCP download mode)")
else()
    # 动态链接
    target_link_libraries(${PROJECT_NAME} 
        pthread 
        util 
        dl
        ssl
        crypto
        z
    )
    message(STATUS "Using dynamic linking without libcurl (TCP download mode)")
endif()

# 安装规则
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION bin
)

# 打包规则
set(CPACK_PACKAGE_NAME "buildroot-agent")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Buildroot Agent - TCP download version")
set(CPACK_GENERATOR "TGZ")

include(CPack)