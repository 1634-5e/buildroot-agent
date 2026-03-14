/**
 * @file twin_diff.h
 * @brief Device Twin 差异计算模块
 * 
 * 计算 desired 和 reported 之间的差异
 */

#ifndef TWIN_DIFF_H
#define TWIN_DIFF_H

#include <stdbool.h>
#include <cjson/cJSON.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 计算两个 JSON 对象的差异
 * 
 * 返回 desired 中存在但 reported 中不存在或不同的字段
 * 
 * @param desired 期望状态
 * @param reported 已报告状态
 * @return 差异 JSON 对象 (需要调用者释放), NULL 表示无差异或错误
 */
cJSON* twin_diff_compute(cJSON* desired, cJSON* reported);

/**
 * @brief 合并两个 JSON 对象
 * 
 * 将 overlay 合并到 base 中，返回新对象
 * 
 * @param base 基础对象
 * @param overlay 覆盖对象
 * @return 合并后的 JSON 对象 (需要调用者释放)
 */
cJSON* twin_diff_merge(cJSON* base, cJSON* overlay);

/**
 * @brief 检查两个 JSON 对象是否相等
 * 
 * @param a 第一个对象
 * @param b 第二个对象
 * @return true 相等, false 不相等
 */
bool twin_diff_equal(cJSON* a, cJSON* b);

#ifdef __cplusplus
}
#endif

#endif /* TWIN_DIFF_H */