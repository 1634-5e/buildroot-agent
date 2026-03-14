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
    use pretty_assertions::assert_eq;
    use serde_json::json;

    // ============ DeviceTwin 基础测试 ============

    #[test]
    fn test_twin_new() {
        let twin = DeviceTwin::new("device-001");
        assert_eq!(twin.device_id, "device-001");
        assert_eq!(twin.desired, json!({}));
        assert_eq!(twin.reported, json!({}));
        assert_eq!(twin.desired_version, 0);
        assert_eq!(twin.reported_version, 0);
    }

    #[test]
    fn test_twin_default() {
        let twin = DeviceTwin::default();
        assert!(twin.device_id.is_empty());
        assert!(twin.is_synced()); // 空 twin 应该是同步的
    }

    // ============ Delta 计算测试 ============

    #[test]
    fn test_compute_delta_basic() {
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
        assert!(delta.get("config").unwrap().get("interval").is_none(), "相同的值不应出现在 delta 中");
    }

    #[test]
    fn test_compute_delta_synced() {
        let desired = json!({
            "firmware": {"version": "1.0.0"},
            "config": {"interval": 60}
        });
        let reported = desired.clone();

        let delta = DeviceTwin::compute_delta(&desired, &reported);
        assert!(delta.as_object().unwrap().is_empty(), "完全同步时 delta 应为空");
    }

    #[test]
    fn test_compute_delta_missing_in_reported() {
        let desired = json!({
            "firmware": {"version": "2.0.0"},
            "config": {"interval": 60}
        });
        let reported = json!({
            "firmware": {"version": "2.0.0"}
        });

        let delta = DeviceTwin::compute_delta(&desired, &reported);

        // config 在 reported 中不存在，应该在 delta 中
        assert!(delta.get("config").is_some());
        assert_eq!(delta["config"]["interval"], 60);
    }

    #[test]
    fn test_compute_delta_nested() {
        let desired = json!({
            "network": {
                "wifi": {
                    "ssid": "MyNetwork",
                    "password": "secret123"
                },
                "ethernet": {
                    "dhcp": true
                }
            }
        });
        let reported = json!({
            "network": {
                "wifi": {
                    "ssid": "OldNetwork",
                    "password": "secret123"
                },
                "ethernet": {
                    "dhcp": false
                }
            }
        });

        let delta = DeviceTwin::compute_delta(&desired, &reported);

        // wifi.ssid 不同
        assert_eq!(delta["network"]["wifi"]["ssid"], "MyNetwork");
        // wifi.password 相同，不应出现
        assert!(delta["network"]["wifi"].get("password").is_none());
        // ethernet.dhcp 不同
        assert_eq!(delta["network"]["ethernet"]["dhcp"], true);
    }

    #[test]
    fn test_compute_delta_empty_desired() {
        let desired = json!({});
        let reported = json!({"firmware": {"version": "1.0.0"}});

        let delta = DeviceTwin::compute_delta(&desired, &reported);
        assert!(delta.as_object().unwrap().is_empty(), "空 desired 应产生空 delta");
    }

    #[test]
    fn test_compute_delta_empty_reported() {
        let desired = json!({
            "firmware": {"version": "2.0.0"},
            "config": {"interval": 60}
        });
        let reported = json!({});

        let delta = DeviceTwin::compute_delta(&desired, &reported);

        // 所有 desired 内容都应该在 delta 中
        assert_eq!(delta, desired);
    }

    #[test]
    fn test_compute_delta_non_object_values() {
        let desired = json!({
            "version": "2.0.0",
            "enabled": true,
            "count": 42
        });
        let reported = json!({
            "version": "1.0.0",
            "enabled": true,
            "count": 42
        });

        let delta = DeviceTwin::compute_delta(&desired, &reported);

        // 只有 version 不同
        assert_eq!(delta["version"], "2.0.0");
        assert!(delta.get("enabled").is_none());
        assert!(delta.get("count").is_none());
    }

    #[test]
    fn test_compute_delta_array_values() {
        let desired = json!({
            "tags": ["production", "critical"],
            "config": {"name": "test"}
        });
        let reported = json!({
            "tags": ["staging"],
            "config": {"name": "test"}
        });

        let delta = DeviceTwin::compute_delta(&desired, &reported);

        // 数组比较是整体比较
        assert_eq!(delta["tags"], json!(["production", "critical"]));
    }

    // ============ is_synced 测试 ============

    #[test]
    fn test_is_synced_when_equal() {
        let mut twin = DeviceTwin::new("test-001");
        twin.desired = json!({"version": "1.0.0"});
        twin.reported = json!({"version": "1.0.0"});
        assert!(twin.is_synced());
    }

    #[test]
    fn test_is_synced_when_different() {
        let mut twin = DeviceTwin::new("test-001");
        twin.desired = json!({"version": "1.0.0"});
        twin.reported = json!({"version": "0.9.0"});
        assert!(!twin.is_synced());
    }

    #[test]
    fn test_is_synced_when_reported_missing_key() {
        let mut twin = DeviceTwin::new("test-001");
        twin.desired = json!({"version": "1.0.0", "config": {"interval": 60}});
        twin.reported = json!({"version": "1.0.0"});
        assert!(!twin.is_synced(), "reported 缺少 config，应该不同步");
    }

    #[test]
    fn test_is_synced_when_reported_has_extra_keys() {
        let mut twin = DeviceTwin::new("test-001");
        twin.desired = json!({"version": "1.0.0"});
        twin.reported = json!({"version": "1.0.0", "extra": "value"});
        assert!(twin.is_synced(), "reported 有额外的 key 不影响同步状态");
    }

    #[test]
    fn test_is_synced_empty() {
        let twin = DeviceTwin::new("test-001");
        assert!(twin.is_synced(), "空 Twin 应该是同步的");
    }

    // ============ TwinOverview 测试 ============

    #[test]
    fn test_twin_overview_from_twin() {
        let mut twin = DeviceTwin::new("device-001");
        twin.desired = json!({"version": "2.0.0"});
        twin.reported = json!({"version": "1.0.0"});
        twin.tags = json!({"location": "datacenter"});

        let overview = TwinOverview::from(twin.clone());

        assert_eq!(overview.device_id, twin.device_id);
        assert_eq!(overview.desired, twin.desired);
        assert_eq!(overview.reported, twin.reported);
        assert_eq!(overview.delta, json!({"version": "2.0.0"}));
        assert!(!overview.is_synced);
    }

    #[test]
    fn test_twin_overview_synced() {
        let mut twin = DeviceTwin::new("device-001");
        twin.desired = json!({"version": "1.0.0"});
        twin.reported = json!({"version": "1.0.0"});

        let overview = TwinOverview::from(twin);

        assert!(overview.is_synced);
        assert!(overview.delta.as_object().unwrap().is_empty());
    }

    // ============ 序列化/反序列化测试 ============

    #[test]
    fn test_twin_serialize_deserialize() {
        let mut twin = DeviceTwin::new("device-001");
        twin.desired = json!({"firmware": {"version": "2.0.0"}});
        twin.reported = json!({"firmware": {"version": "1.0.0"}});
        twin.tags = json!({"type": "sensor"});

        let json = serde_json::to_string(&twin).unwrap();
        let decoded: DeviceTwin = serde_json::from_str(&json).unwrap();

        assert_eq!(decoded.device_id, twin.device_id);
        assert_eq!(decoded.desired, twin.desired);
        assert_eq!(decoded.reported, twin.reported);
    }

    #[test]
    fn test_register_request_deserialize() {
        let json = r#"{
            "device_id": "custom-001",
            "device_name": "Temperature Sensor",
            "device_type": "sensor",
            "tags": {"location": "room-101"}
        }"#;

        let req: DeviceRegisterRequest = serde_json::from_str(json).unwrap();

        assert_eq!(req.device_id, Some("custom-001".to_string()));
        assert_eq!(req.device_name, Some("Temperature Sensor".to_string()));
        assert_eq!(req.device_type, Some("sensor".to_string()));
        assert_eq!(req.tags["location"], "room-101");
    }

    #[test]
    fn test_register_request_defaults() {
        let json = r#"{}"#;

        let req: DeviceRegisterRequest = serde_json::from_str(json).unwrap();

        assert!(req.device_id.is_none());
        assert!(req.device_name.is_none());
        assert!(req.tags.is_null() || req.tags == json!({}));
    }

    #[test]
    fn test_batch_update_result_serialize() {
        let result = BatchUpdateResult {
            updated: 10,
            failed: 2,
            device_ids: vec!["device-001".to_string(), "device-002".to_string()],
        };

        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"updated\":10"));
        assert!(json.contains("\"failed\":2"));
    }

    #[test]
    fn test_change_log_serialize() {
        let log = ChangeLog {
            id: 1,
            device_id: "device-001".to_string(),
            change_type: "desired".to_string(),
            old_value: json!({"version": "1.0.0"}),
            new_value: json!({"version": "2.0.0"}),
            changed_by: Some("admin".to_string()),
            changed_at: chrono::Utc::now(),
        };

        let json = serde_json::to_string(&log).unwrap();
        assert!(json.contains("\"change_type\":\"desired\""));
    }
}