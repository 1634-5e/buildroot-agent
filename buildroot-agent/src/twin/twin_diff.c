/**
 * @file twin_diff.c
 * @brief Device Twin 差异计算模块实现
 */

#include "twin/twin_diff.h"
#include <stdbool.h>
#include <string.h>

/* ==================== 公开函数实现 ==================== */

cJSON* twin_diff_compute(cJSON* desired, cJSON* reported) {
    if (!desired) {
        return cJSON_CreateObject();  /* 无差异 */
    }
    
    if (!reported) {
        return cJSON_Duplicate(desired, 1);  /* 全部是差异 */
    }
    
    cJSON* delta = cJSON_CreateObject();
    if (!delta) {
        return NULL;
    }
    
    /* 遍历 desired 的所有字段 */
    cJSON* item = NULL;
    cJSON_ArrayForEach(item, desired) {
        const char* key = item->string;
        cJSON* reported_item = cJSON_GetObjectItem(reported, key);
        
        if (!reported_item) {
            /* reported 中不存在该字段 -> 加入差异 */
            cJSON* new_item = cJSON_Duplicate(item, 1);
            if (new_item) {
                cJSON_AddItemToObject(delta, key, new_item);
            }
        } else if (!twin_diff_equal(item, reported_item)) {
            /* 值不同 */
            if (cJSON_IsObject(item) && cJSON_IsObject(reported_item)) {
                /* 递归比较嵌套对象 */
                cJSON* nested_delta = twin_diff_compute(item, reported_item);
                if (nested_delta && cJSON_GetArraySize(nested_delta) > 0) {
                    cJSON_AddItemToObject(delta, key, nested_delta);
                } else if (nested_delta) {
                    cJSON_Delete(nested_delta);
                }
            } else {
                /* 非对象类型，直接加入差异 */
                cJSON* new_item = cJSON_Duplicate(item, 1);
                if (new_item) {
                    cJSON_AddItemToObject(delta, key, new_item);
                }
            }
        }
        /* 值相同 -> 不加入差异 */
    }
    
    return delta;
}

cJSON* twin_diff_merge(cJSON* base, cJSON* overlay) {
    if (!base && !overlay) {
        return cJSON_CreateObject();
    }
    if (!base) {
        return cJSON_Duplicate(overlay, 1);
    }
    if (!overlay) {
        return cJSON_Duplicate(base, 1);
    }
    
    cJSON* result = cJSON_Duplicate(base, 1);
    if (!result) {
        return NULL;
    }
    
    /* 遍历 overlay */
    cJSON* item = NULL;
    cJSON_ArrayForEach(item, overlay) {
        const char* key = item->string;
        cJSON* base_item = cJSON_GetObjectItem(result, key);
        
        if (base_item && cJSON_IsObject(base_item) && cJSON_IsObject(item)) {
            /* 递归合并 */
            cJSON* nested = twin_diff_merge(base_item, item);
            if (nested) {
                cJSON_ReplaceItemInObject(result, key, nested);
            }
        } else {
            /* 替换或添加 */
            cJSON* new_item = cJSON_Duplicate(item, 1);
            if (new_item) {
                cJSON_ReplaceItemInObject(result, key, new_item);
            }
        }
    }
    
    return result;
}

bool twin_diff_equal(cJSON* a, cJSON* b) {
    if (!a && !b) {
        return true;
    }
    if (!a || !b) {
        return false;
    }
    if (a->type != b->type) {
        return false;
    }
    
    switch (a->type) {
        case cJSON_False:
        case cJSON_True:
            return true;  /* 类型相同，值必然相同 */
            
        case cJSON_NULL:
            return true;
            
        case cJSON_Number:
            /* 使用 cJSON 的比较，考虑浮点精度 */
            return cJSON_Compare(a, b, true);
            
        case cJSON_String:
            return strcmp(a->valuestring, b->valuestring) == 0;
            
        case cJSON_Array: {
            int size_a = cJSON_GetArraySize(a);
            int size_b = cJSON_GetArraySize(b);
            if (size_a != size_b) {
                return false;
            }
            for (int i = 0; i < size_a; i++) {
                cJSON* item_a = cJSON_GetArrayItem(a, i);
                cJSON* item_b = cJSON_GetArrayItem(b, i);
                if (!twin_diff_equal(item_a, item_b)) {
                    return false;
                }
            }
            return true;
        }
        
        case cJSON_Object: {
            int size_a = cJSON_GetArraySize(a);
            int size_b = cJSON_GetArraySize(b);
            if (size_a != size_b) {
                return false;
            }
            cJSON* item = NULL;
            cJSON_ArrayForEach(item, a) {
                cJSON* item_b = cJSON_GetObjectItem(b, item->string);
                if (!twin_diff_equal(item, item_b)) {
                    return false;
                }
            }
            return true;
        }
        
        default:
            return false;
    }
}