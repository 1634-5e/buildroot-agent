/*
 * 工具函数测试
 */

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include "agent.h"

/* 测试 base64_decode */
static void test_base64_decode(void **state) {
    (void) state;
    
    /* 测试基本 base64 解码 */
    const char *encoded = "SGVsbG8gV29ybGQ=";  /* "Hello World" */
    unsigned char decoded[32];
    
    size_t result = base64_decode(encoded, decoded);
    
    assert_int_equal(result, 11);
    assert_memory_equal(decoded, "Hello World", 11);
}

/* 测试 safe_strncpy */
static void test_safe_strncpy(void **state) {
    (void) state;
    
    char dest[10];
    const char *src = "Hello World";
    
    safe_strncpy(dest, src, sizeof(dest));
    
    /* 应该被截断到 9 个字符 + null */
    assert_int_equal(strlen(dest), 9);
    assert_string_equal(dest, "Hello Wor");
}
