/*
 * Agent JSON/工具函数单元测试（独立版本）
 * 不依赖 agent_protocol.c 中的全局变量
 */

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <ctype.h>
#include <unistd.h>
#include <sys/stat.h>

/* ========== 被测函数实现 ========== */

/* Base64 解码表 */
static const signed char base64_decode_table[128] = {
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,62,-1,-1,-1,63,
    52,53,54,55,56,57,58,59,60,61,-1,-1,-1,-1,-1,-1,
    -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,
    15,16,17,18,19,20,21,22,23,24,25,-1,-1,-1,-1,-1,
    -1,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,-1,-1,-1,-1,-1
};

static size_t base64_decode(const char *input, unsigned char *output) {
    size_t input_len = strlen(input);
    size_t output_len = 0;
    int val = 0, valb = -8;

    for (size_t i = 0; i < input_len; i++) {
        char c = input[i];
        if (c == '=') break;
        if ((c < 0) || (c > 127) || (base64_decode_table[(int)c] < 0)) continue;

        val = (val << 6) + base64_decode_table[(int)c];
        valb += 6;
        if (valb >= 0) {
            output[output_len++] = (val >> valb) & 0xFF;
            valb -= 8;
        }
    }
    return output_len;
}

static void safe_strncpy(char *dest, const char *src, size_t size) {
    if (!dest || !src || size == 0) return;
    size_t i;
    for (i = 0; i < size - 1 && src[i]; i++) {
        dest[i] = src[i];
    }
    dest[i] = '\0';
}

static bool file_exists(const char *path) {
    struct stat st;
    return (stat(path, &st) == 0);
}

/* 简单的 JSON 解析函数 */
static char *json_get_string(const char *json, const char *key) {
    if (!json || !key) return NULL;
    
    char key_pattern[256];
    snprintf(key_pattern, sizeof(key_pattern), "\"%s\":\"", key);
    
    const char *start = strstr(json, key_pattern);
    if (!start) return NULL;
    
    start += strlen(key_pattern);
    const char *end = strchr(start, '"');
    if (!end) return NULL;
    
    size_t len = end - start;
    char *result = malloc(len + 1);
    if (!result) return NULL;
    
    memcpy(result, start, len);
    result[len] = '\0';
    return result;
}

static int json_get_int(const char *json, const char *key, int default_val) {
    if (!json || !key) return default_val;
    
    char key_pattern[256];
    snprintf(key_pattern, sizeof(key_pattern), "\"%s\":", key);
    
    const char *start = strstr(json, key_pattern);
    if (!start) return default_val;
    
    start += strlen(key_pattern);
    return atoi(start);
}

static bool json_get_bool(const char *json, const char *key, bool default_val) {
    if (!json || !key) return default_val;
    
    char key_pattern[256];
    snprintf(key_pattern, sizeof(key_pattern), "\"%s\":", key);
    
    const char *start = strstr(json, key_pattern);
    if (!start) return default_val;
    
    start += strlen(key_pattern);
    while (isspace(*start)) start++;
    
    if (strncmp(start, "true", 4) == 0) return true;
    if (strncmp(start, "false", 5) == 0) return false;
    return default_val;
}

/* ========== 测试用例 ========== */

static void test_json_get_string_basic(void **state) {
    (void) state;
    const char *json = "{\"name\":\"test_device\",\"version\":\"1.0.0\"}";
    char *result = json_get_string(json, "name");
    assert_non_null(result);
    assert_string_equal(result, "test_device");
    free(result);
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
    free(result);
}

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
    assert_true(result);
}

static void test_base64_decode_basic(void **state) {
    (void) state;
    const char *encoded = "SGVsbG8gV29ybGQ=";
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

static void test_file_exists_true(void **state) {
    (void) state;
    bool result = file_exists("/etc/passwd");
    assert_true(result);
}

static void test_file_exists_false(void **state) {
    (void) state;
    bool result = file_exists("/nonexistent/file/path");
    assert_false(result);
}

/* 主函数 */
int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_json_get_string_basic),
        cmocka_unit_test(test_json_get_string_not_found),
        cmocka_unit_test(test_json_get_string_empty),
        cmocka_unit_test(test_json_get_int_basic),
        cmocka_unit_test(test_json_get_int_not_found),
        cmocka_unit_test(test_json_get_int_negative),
        cmocka_unit_test(test_json_get_bool_true),
        cmocka_unit_test(test_json_get_bool_false),
        cmocka_unit_test(test_json_get_bool_not_found),
        cmocka_unit_test(test_base64_decode_basic),
        cmocka_unit_test(test_base64_decode_empty),
        cmocka_unit_test(test_safe_strncpy_basic),
        cmocka_unit_test(test_safe_strncpy_truncate),
        cmocka_unit_test(test_safe_strncpy_exact_fit),
        cmocka_unit_test(test_file_exists_true),
        cmocka_unit_test(test_file_exists_false),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
