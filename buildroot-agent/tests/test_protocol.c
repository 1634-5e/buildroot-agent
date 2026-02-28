/*
 * Agent Protocol 模块单元测试
 * 使用 CMocka 测试框架
 */

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 包含被测函数声明 */
#include "../include/agent.h"

/* 测试 JSON 解析函数 - json_get_string */
static void test_json_get_string_basic(void **state) {
    (void) state;
    
    const char *json = "{\"name\":\"test_device\",\"version\":\"1.0.0\"}";
    char *result = json_get_string(json, "name");
    
    assert_non_null(result);
    assert_string_equal(result, "test_device");
    
    if (result) free(result);
}

static void test_json_get_string_not_found(void **state) {
    (void) state;
    
    const char *json = "{\"name\":\"test\"}";
    char *result = json_get_string(json, "nonexistent");
    
    assert_null(result);
}

static void test_json_get_string_empty(void **state) {
    (void) state;
    
    const char *json = "{\"name\":\"\"}";
    char *result = json_get_string(json, "name");
    
    assert_non_null(result);
    assert_string_equal(result, "");
    
    if (result) free(result);
}

/* 测试 JSON 解析函数 - json_get_int */
static void test_json_get_int_basic(void **state) {
    (void) state;
    
    const char *json = "{\"count\":42,\"total\":100}";
    int result = json_get_int(json, "count", 0);
    
    assert_int_equal(result, 42);
}

static void test_json_get_int_not_found(void **state) {
    (void) state;
    
    const char *json = "{\"count\":42}";
    int result = json_get_int(json, "missing", -1);
    
    assert_int_equal(result, -1);
}

static void test_json_get_int_negative(void **state) {
    (void) state;
    
    const char *json = "{\"value\":-123}";
    int result = json_get_int(json, "value", 0);
    
    assert_int_equal(result, -123);
}

/* 测试 JSON 解析函数 - json_get_bool */
static void test_json_get_bool_true(void **state) {
    (void) state;
    
    const char *json = "{\"enabled\":true}";
    bool result = json_get_bool(json, "enabled", false);
    
    assert_true(result);
}

static void test_json_get_bool_false(void **state) {
    (void) state;
    
    const char *json = "{\"disabled\":false}";
    bool result = json_get_bool(json, "disabled", true);
    
    assert_false(result);
}

static void test_json_get_bool_not_found(void **state) {
    (void) state;
    
    const char *json = "{\"other\":true}";
    bool result = json_get_bool(json, "missing", true);
    
    assert_true(result);  /* 应该返回默认值 */
}

/* 测试 base64 解码 */
static void test_base64_decode_basic(void **state) {
    (void) state;
    
    const char *encoded = "SGVsbG8gV29ybGQ=";  /* "Hello World" */
    unsigned char decoded[32];
    
    size_t result = base64_decode(encoded, decoded);
    
    assert_int_equal(result, 11);
    assert_memory_equal(decoded, "Hello World", 11);
}

static void test_base64_decode_empty(void **state) {
    (void) state;
    
    const char *encoded = "";
    unsigned char decoded[32];
    
    size_t result = base64_decode(encoded, decoded);
    
    assert_int_equal(result, 0);
}

/* 测试 safe_strncpy */
static void test_safe_strncpy_basic(void **state) {
    (void) state;
    
    char dest[10];
    const char *src = "Hello";
    
    safe_strncpy(dest, src, sizeof(dest));
    
    assert_string_equal(dest, "Hello");
}

static void test_safe_strncpy_truncate(void **state) {
    (void) state;
    
    char dest[10];
    const char *src = "Hello World This Is Long";
    
    safe_strncpy(dest, src, sizeof(dest));
    
    /* 应该被截断，并且以 null 结尾 */
    assert_int_equal(strlen(dest), 9);
    assert_string_equal(dest, "Hello Wor");
}

static void test_safe_strncpy_exact_fit(void **state) {
    (void) state;
    
    char dest[6];
    const char *src = "Hello";
    
    safe_strncpy(dest, src, sizeof(dest));
    
    assert_string_equal(dest, "Hello");
}

/* 测试消息类型定义 */
static void test_message_types(void **state) {
    (void) state;
    
    /* 验证关键消息类型值 */
    assert_int_equal(MSG_TYPE_HEARTBEAT, 0x01);
    assert_int_equal(MSG_TYPE_REGISTER, 0xF0);
    assert_int_equal(MSG_TYPE_REGISTER_RESULT, 0xF1);
    assert_int_equal(MSG_TYPE_SYSTEM_STATUS, 0x02);
}

/* 测试工具函数 - file_exists */
static void test_file_exists_true(void **state) {
    (void) state;
    
    /* 测试存在的文件 */
    bool result = file_exists("/etc/passwd");
    
    assert_true(result);
}

static void test_file_exists_false(void **state) {
    (void) state;
    
    /* 测试不存在的文件 */
    bool result = file_exists("/nonexistent/file/path");
    
    assert_false(result);
}

/* 主函数 */
int main(void) {
    const struct CMUnitTest tests[] = {
        /* JSON 解析测试 */
        cmocka_unit_test(test_json_get_string_basic),
        cmocka_unit_test(test_json_get_string_not_found),
        cmocka_unit_test(test_json_get_string_empty),
        cmocka_unit_test(test_json_get_int_basic),
        cmocka_unit_test(test_json_get_int_not_found),
        cmocka_unit_test(test_json_get_int_negative),
        cmocka_unit_test(test_json_get_bool_true),
        cmocka_unit_test(test_json_get_bool_false),
        cmocka_unit_test(test_json_get_bool_not_found),
        
        /* Base64 测试 */
        cmocka_unit_test(test_base64_decode_basic),
        cmocka_unit_test(test_base64_decode_empty),
        
        /* 字符串工具测试 */
        cmocka_unit_test(test_safe_strncpy_basic),
        cmocka_unit_test(test_safe_strncpy_truncate),
        cmocka_unit_test(test_safe_strncpy_exact_fit),
        
        /* 消息类型测试 */
        cmocka_unit_test(test_message_types),
        
        /* 文件工具测试 */
        cmocka_unit_test(test_file_exists_true),
        cmocka_unit_test(test_file_exists_false),
    };
    
    return cmocka_run_group_tests(tests, NULL, NULL);
}
