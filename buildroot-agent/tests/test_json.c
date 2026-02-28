/*
 * JSON 解析工具测试
 */

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include "agent.h"

/* 测试 json_get_string */
static void test_json_get_string(void **state) {
    (void) state;
    
    const char *json = "{\"name\":\"test\",\"value\":123}";
    char *result = json_get_string(json, "name");
    
    assert_non_null(result);
    assert_string_equal(result, "test");
    
    free(result);
}

/* 测试 json_get_int */
static void test_json_get_int(void **state) {
    (void) state;
    
    const char *json = "{\"count\":42,\"enabled\":true}";
    int result = json_get_int(json, "count", 0);
    
    assert_int_equal(result, 42);
}

/* 测试 json_get_bool */
static void test_json_get_bool(void **state) {
    (void) state;
    
    const char *json = "{\"enabled\":true,\"disabled\":false}";
    bool enabled = json_get_bool(json, "enabled", false);
    bool disabled = json_get_bool(json, "disabled", true);
    
    assert_true(enabled);
    assert_false(disabled);
}
