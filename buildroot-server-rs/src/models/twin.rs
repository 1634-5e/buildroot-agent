//! Device Twin 数据模型

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// 设备 Twin
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceTwin {
    pub device_id: String,
    pub desired: serde_json::Value,
    pub desired_version: i64,
    pub reported: serde_json::Value,
    pub reported_version: i64,
    pub tags: serde_json::Value,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
}

impl Default for DeviceTwin {
    fn default() -> Self {
        Self {
            device_id: String::new(),
            desired: serde_json::json!({}),
            desired_version: 0,
            reported: serde_json::json!({}),
            reported_version: 0,
            tags: serde_json::json!({}),
            created_at: None,
            updated_at: None,
        }
    }
}

impl DeviceTwin {
    /// 创建新的 Twin
    pub fn new(device_id: impl Into<String>) -> Self {
        Self {
            device_id: device_id.into(),
            ..Default::default()
        }
    }

    /// 计算 desired 和 reported 的差异
    pub fn delta(&self) -> serde_json::Value {
        Self::compute_delta(&self.desired, &self.reported)
    }

    /// 是否已同步（delta 为空）
    pub fn is_synced(&self) -> bool {
        self.delta().as_object().map_or(true, |obj| obj.is_empty())
    }

    /// 递归计算差异
    fn compute_delta(desired: &serde_json::Value, reported: &serde_json::Value) -> serde_json::Value {
        let desired_obj = match desired.as_object() {
            Some(obj) => obj,
            None => return serde_json::json!({}),
        };
        let empty_map = serde_json::Map::new();
        let reported_obj = reported.as_object().unwrap_or(&empty_map);

        let mut delta = serde_json::Map::new();

        for (key, desired_value) in desired_obj {
            let reported_value = reported_obj.get(key);

            match (desired_value, reported_value) {
                // 两者都是对象，递归计算
                (serde_json::Value::Object(d_obj), Some(serde_json::Value::Object(r_obj))) => {
                    let nested = Self::compute_delta(&serde_json::Value::Object(d_obj.clone()), &serde_json::Value::Object(r_obj.clone()));
                    if nested.as_object().map_or(false, |o| !o.is_empty()) {
                        delta.insert(key.clone(), nested);
                    }
                }
                // reported 中没有这个 key
                (_, None) => {
                    delta.insert(key.clone(), desired_value.clone());
                }
                // 值不同
                (_, Some(r_val)) if desired_value != r_val => {
                    delta.insert(key.clone(), desired_value.clone());
                }
                // 值相同，跳过
                _ => {}
            }
        }

        serde_json::Value::Object(delta)
    }
}

/// Twin 概览（含 delta）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TwinOverview {
    pub device_id: String,
    pub desired: serde_json::Value,
    pub desired_version: i64,
    pub reported: serde_json::Value,
    pub reported_version: i64,
    pub tags: serde_json::Value,
    pub delta: serde_json::Value,
    pub is_synced: bool,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
}

impl From<DeviceTwin> for TwinOverview {
    fn from(twin: DeviceTwin) -> Self {
        let delta = twin.delta();
        let is_synced = twin.is_synced();
        Self {
            device_id: twin.device_id,
            desired: twin.desired,
            desired_version: twin.desired_version,
            reported: twin.reported,
            reported_version: twin.reported_version,
            tags: twin.tags,
            delta,
            is_synced,
            created_at: twin.created_at,
            updated_at: twin.updated_at,
        }
    }
}

/// Twin 更新请求
#[derive(Debug, Clone, Deserialize)]
pub struct TwinUpdate {
    pub desired: serde_json::Value,
}

/// 变更日志
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeLog {
    pub id: i64,
    pub device_id: String,
    pub change_type: String,
    pub old_value: serde_json::Value,
    pub new_value: serde_json::Value,
    pub changed_by: Option<String>,
    pub changed_at: DateTime<Utc>,
}

/// 批量更新请求
#[derive(Debug, Clone, Deserialize)]
pub struct BatchUpdate {
    pub device_ids: Option<Vec<String>>,
    pub filters: Option<serde_json::Value>,
    pub desired: serde_json::Value,
}

/// 批量更新结果
#[derive(Debug, Clone, Serialize)]
pub struct BatchUpdateResult {
    pub updated: u64,
    pub failed: u64,
    pub device_ids: Vec<String>,
}

/// 设备注册请求
#[derive(Debug, Clone, Deserialize)]
pub struct DeviceRegisterRequest {
    pub device_id: Option<String>,
    pub device_name: Option<String>,
    pub device_type: Option<String>,
    pub firmware_version: Option<String>,
    pub hardware_version: Option<String>,
    pub mac_address: Option<String>,
    #[serde(default)]
    pub tags: serde_json::Value,
}

/// 设备注册响应
#[derive(Debug, Clone, Serialize)]
pub struct DeviceRegisterResponse {
    pub device_id: String,
    pub mqtt_username: String,
    pub mqtt_password: String,
    pub mqtt_broker: String,
    pub mqtt_port: u16,
    pub created: bool,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_compute_delta() {
        let desired = json!({
            "firmware": {"version": "2.0.0"},
            "config": {"interval": 60, "logLevel": "debug"}
        });
        let reported = json!({
            "firmware": {"version": "1.0.0"},
            "config": {"interval": 60, "logLevel": "info"}
        });

        let delta = DeviceTwin::compute_delta(&desired, &reported);

        assert_eq!(delta["firmware"]["version"], "2.0.0");
        assert_eq!(delta["config"]["logLevel"], "debug");
        assert!(delta.get("config").unwrap().get("interval").is_none());
    }

    #[test]
    fn test_is_synced() {
        let mut twin = DeviceTwin::new("test-001");
        twin.desired = json!({"version": "1.0.0"});
        twin.reported = json!({"version": "1.0.0"});
        assert!(twin.is_synced());

        twin.reported = json!({"version": "0.9.0"});
        assert!(!twin.is_synced());
    }
}