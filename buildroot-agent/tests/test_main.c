/*
 * Buildroot Agent 测试框架
 * 使用 CMocka 单元测试框架
 */

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include "agent.h"

/* 必需：CMocka 的 main 函数 */
int main(void) {
    const struct CMUnitTest tests[] = {
        /* 协议测试 */
        cmocka_unit_test(test_protocol_encode_message),
        cmocka_unit_test(test_protocol_decode_message),
        cmocka_unit_test(test_protocol_heartbeat),
        cmocka_unit_test(test_protocol_register),
        
        /* Socket 测试 */
        cmocka_unit_test(test_socket_connect),
        cmocka_unit_test(test_socket_send),
        cmocka_unit_test(test_socket_reconnect),
        
        /* JSON 解析测试 */
        cmocka_unit_test(test_json_get_string),
        cmocka_unit_test(test_json_get_int),
        cmocka_unit_test(test_json_get_bool),
        
        /* 工具函数测试 */
        cmocka_unit_test(test_base64_decode),
        cmocka_unit_test(test_safe_strncpy),
    };
    
    return cmocka_run_group_tests(tests, NULL, NULL);
}
