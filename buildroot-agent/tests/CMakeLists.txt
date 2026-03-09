# Agent 单元测试 CMake 配置
# 使用 CMocka 测试框架

cmake_minimum_required(VERSION 2.8.12)

# 查找 CMocka
find_package(PkgConfig QUIET)
if(PKG_CONFIG_FOUND)
    pkg_check_modules(CMOCKA cmocka)
endif()

if(NOT CMOCKA_FOUND)
    find_library(CMOCKA_LIBRARY cmocka)
    find_path(CMOCKA_INCLUDE_DIR cmocka.h)
    if(CMOCKA_LIBRARY AND CMOCKA_INCLUDE_DIR)
        set(CMOCKA_FOUND TRUE)
        set(CMOCKA_LIBRARIES ${CMOCKA_LIBRARY})
        set(CMOCKA_INCLUDE_DIRS ${CMOCKA_INCLUDE_DIR})
    endif()
endif()

if(CMOCKA_FOUND)
    message(STATUS "CMocka found: ${CMOCKA_LIBRARIES}")
    include_directories(${CMOCKA_INCLUDE_DIRS})
    
    # 测试文件列表
    set(TEST_SOURCES "")
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/test_json_standalone.c")
        list(APPEND TEST_SOURCES test_json_standalone.c)
    endif()
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/test_socket.c")
        list(APPEND TEST_SOURCES test_socket.c)
    endif()
    
    # 为每个测试文件创建可执行文件
    # 测试文件自己包含需要的函数实现
    foreach(TEST_FILE ${TEST_SOURCES})
        get_filename_component(TEST_NAME ${TEST_FILE} NAME_WE)
        add_executable(${TEST_NAME} ${TEST_FILE})
        target_include_directories(${TEST_NAME} PRIVATE 
            ${PROJECT_SOURCE_DIR}/include
            ${PROJECT_SOURCE_DIR}/third_party/libconfig/lib
        )
        target_link_libraries(${TEST_NAME} 
            ${CMOCKA_LIBRARIES}
            pthread util dl config
        )
        add_test(NAME ${TEST_NAME} COMMAND ${TEST_NAME})
    endforeach()
    
    # 创建测试目标
    if(TEST_SOURCES)
        add_custom_target(check
            COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
            DEPENDS ${TEST_EXECUTABLES}
        )
    endif()
    
else()
    message(WARNING "CMocka not found, tests will not be built")
    message(WARNING "Install cmocka: apt-get install libcmocka-dev")
endif()
