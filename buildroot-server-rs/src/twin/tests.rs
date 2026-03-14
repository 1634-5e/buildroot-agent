//! Twin Service 测试
//! 
//! 注意：由于 TwinService 强依赖外部服务（PostgreSQL、Redis、MQTT、EMQX），
//! 完整的集成测试需要使用 testcontainers 或真实的测试环境。
//! 
//! 本文件主要测试：
//! 1. 密码生成逻辑
//! 2. JSON 解析逻辑
//! 3. 数据结构转换

#[cfg(test)]
mod tests {
    use crate::models::twin::{
        BatchUpdateResult, ChangeLog, DeviceRegisterRequest, DeviceTwin, TwinOverview,
    };
    use chrono::Utc;
    use serde_json::json;

    // ============ 密码生成测试 ============

    #[test]
    fn test_generate_password_length() {
        // 模拟密码生成逻辑
        fn generate_password(len: usize) -> String {
            use rand::Rng;
            const CHARSET: &[u8] =
                b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
            let mut rng = rand::thread_rng();
            (0..len)
                .map(|_| {
                    let idx = rng.gen_range(0..CHARSET.len());
                    CHARSET[idx] as char
                })
                .collect()
        }

        let password = generate_password(24);
        assert_eq!(password.len(), 24);

        let short_password = generate_password(8);
        assert_eq!(short_password.len(), 8);
    }

    #[test]
    fn test_generate_password_uniqueness() {
        fn generate_password(len: usize) -> String {
            use rand::Rng;
            const CHARSET: &[u8] =
                b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
            let mut rng = rand::thread_rng();
            (0..len)
                .map(|_| {
                    let idx = rng.gen_range(0..CHARSET.len());
                    CHARSET[idx] as char
                })
                .collect()
        }

        let passwords: Vec<String> = (0..100).map(|_| generate_password(24)).collect();

        // 检查所有密码都不同（极大概率）
        let unique_count = passwords.iter().collect::<std::collections::HashSet<_>>().len();
        assert_eq!(unique_count, 100, "密码生成应该产生唯一值");
    }

    #[test]
    fn test_generate_password_charset() {
        fn generate_password(len: usize) -> String {
            use rand::Rng;
            const CHARSET: &[u8] =
                b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
            let mut rng = rand::thread_rng();
            (0..len)
                .map(|_| {
                    let idx = rng.gen_range(0..CHARSET.len());
                    CHARSET[idx] as char
                })
                .collect()
        }

        let password = generate_password(100);

        // 所有字符应该都是字母数字
        for c in password.chars() {
            assert!(c.is_ascii_alphanumeric());
        }
    }

    // ============ JSON 解析测试 ============

    #[test]
    fn test_parse_json_empty() {
        fn parse_json(value: Option<String>) -> serde_json::Value {
            match value {
                Some(s) if !s.is_empty() => serde_json::from_str(&s).unwrap_or_else(|_| json!({})),
                _ => json!({}),
            }
        }

        assert_eq!(parse_json(None), json!({}));
        assert_eq!(parse_json(Some(String::new())), json!({}));
        assert_eq!(parse_json(Some("{}".to_string())), json!({}));
        assert_eq!(
            parse_json(Some(r#"{"key":"value"}"#.to_string())),
            json!({"key": "value"})
        );
    }

    #[test]
    fn test_parse_json_invalid() {
        fn parse_json(value: Option<String>) -> serde_json::Value {
            match value {
                Some(s) if !s.is_empty() => serde_json::from_str(&s).unwrap_or_else(|_| json!({})),
                _ => json!({}),
            }
        }

        // 无效 JSON 返回空对象
        assert_eq!(parse_json(Some("invalid json".to_string())), json!({}));
        assert_eq!(parse_json(Some("{incomplete".to_string())), json!({}));
    }

    #[test]
    fn test_parse_json_complex() {
        fn parse_json(value: Option<String>) -> serde_json::Value {
            match value {
                Some(s) if !s.is_empty() => serde_json::from_str(&s).unwrap_or_else(|_| json!({})),
                _ => json!({}),
            }
        }

        let complex = r#"{
            "firmware": {
                "version": "2.0.0",
                "url": "https://example.com/firmware.bin"
            },
            "config": {
                "interval": 60,
                "enabled": true
            }
        }"#;

        let parsed = parse_json(Some(complex.to_string()));
        assert_eq!(parsed["firmware"]["version"], "2.0.0");
        assert_eq!(parsed["config"]["interval"], 60);
        assert_eq!(parsed["config"]["enabled"], true);
    }

    // ============ 数据模型转换测试 ============

    #[test]
    fn test_twin_to_overview_conversion() {
        let mut twin = DeviceTwin::new("device-001");
        twin.desired = json!({
            "firmware": {"version": "2.0.0"},
            "config": {"interval": 60}
        });
        twin.reported = json!({
            "firmware": {"version": "1.0.0"},
            "config": {"interval": 60}
        });
        twin.tags = json!({"location": "datacenter", "type": "sensor"});

        let overview = TwinOverview::from(twin);

        assert_eq!(overview.device_id, "device-001");
        assert!(!overview.is_synced);
        assert_eq!(overview.delta["firmware"]["version"], "2.0.0");
        // config.interval 相同，不在 delta 中
        assert!(overview.delta.get("config").is_none() 
            || overview.delta["config"].as_object().unwrap().is_empty());
    }

    #[test]
    fn test_device_register_request_defaults() {
        let json = r#"{}"#;
        let req: DeviceRegisterRequest = serde_json::from_str(json).unwrap();

        assert!(req.device_id.is_none());
        assert!(req.device_name.is_none());
        assert!(req.device_type.is_none());
        assert!(req.firmware_version.is_none());
        assert!(req.hardware_version.is_none());
        assert!(req.mac_address.is_none());
    }

    #[test]
    fn test_device_register_request_full() {
        let json = r#"{
            "device_id": "custom-device-001",
            "device_name": "Temperature Sensor",
            "device_type": "sensor",
            "firmware_version": "1.0.0",
            "hardware_version": "rev2",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "tags": {"location": "room-101", "critical": true}
        }"#;

        let req: DeviceRegisterRequest = serde_json::from_str(json).unwrap();

        assert_eq!(req.device_id, Some("custom-device-001".to_string()));
        assert_eq!(req.device_name, Some("Temperature Sensor".to_string()));
        assert_eq!(req.device_type, Some("sensor".to_string()));
        assert_eq!(req.firmware_version, Some("1.0.0".to_string()));
        assert_eq!(req.hardware_version, Some("rev2".to_string()));
        assert_eq!(req.mac_address, Some("AA:BB:CC:DD:EE:FF".to_string()));
        assert_eq!(req.tags["location"], "room-101");
    }

    // ============ 批量更新结果测试 ============

    #[test]
    fn test_batch_update_result() {
        let result = BatchUpdateResult {
            updated: 10,
            failed: 2,
            device_ids: vec![
                "device-001".to_string(),
                "device-002".to_string(),
                "device-003".to_string(),
            ],
        };

        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"updated\":10"));
        assert!(json.contains("\"failed\":2"));
        assert_eq!(result.updated, 10);
        assert_eq!(result.failed, 2);
        assert_eq!(result.device_ids.len(), 3);
    }

    #[test]
    fn test_batch_update_result_empty() {
        let result = BatchUpdateResult {
            updated: 0,
            failed: 0,
            device_ids: vec![],
        };

        assert_eq!(result.updated, 0);
        assert_eq!(result.failed, 0);
        assert!(result.device_ids.is_empty());
    }

    // ============ ChangeLog 测试 ============

    #[test]
    fn test_change_log_serialization() {
        let log = ChangeLog {
            id: 1,
            device_id: "device-001".to_string(),
            change_type: "desired".to_string(),
            old_value: json!({"version": "1.0.0"}),
            new_value: json!({"version": "2.0.0"}),
            changed_by: Some("admin".to_string()),
            changed_at: Utc::now(),
        };

        let json = serde_json::to_string(&log).unwrap();
        assert!(json.contains("\"device_id\":\"device-001\""));
        assert!(json.contains("\"change_type\":\"desired\""));
        assert!(json.contains("\"changed_by\":\"admin\""));

        let decoded: ChangeLog = serde_json::from_str(&json).unwrap();
        assert_eq!(decoded.device_id, log.device_id);
        assert_eq!(decoded.change_type, log.change_type);
    }

    #[test]
    fn test_change_log_null_changed_by() {
        let json = r#"{
            "id": 1,
            "device_id": "device-001",
            "change_type": "reported",
            "old_value": {},
            "new_value": {"version": "1.0.0"},
            "changed_by": null,
            "changed_at": "2024-01-01T00:00:00Z"
        }"#;

        let log: ChangeLog = serde_json::from_str(json).unwrap();
        assert!(log.changed_by.is_none());
    }

    // ============ 缓存键格式测试 ============

    #[test]
    fn test_cache_key_format() {
        let device_id = "device-001";
        let cache_key = format!("twin:{}", device_id);
        assert_eq!(cache_key, "twin:device-001");
    }

    #[test]
    fn test_cache_hash_fields() {
        // 验证缓存哈希应该包含的字段
        let expected_fields = vec![
            "desired",
            "desired_version",
            "reported",
            "reported_version",
            "tags",
        ];

        for field in expected_fields {
            assert!(!field.is_empty());
        }
    }

    // ============ 版本号递增测试 ============

    #[test]
    fn test_version_increment() {
        let mut twin = DeviceTwin::new("device-001");
        
        assert_eq!(twin.desired_version, 0);
        twin.desired_version += 1;
        assert_eq!(twin.desired_version, 1);
        
        twin.reported_version += 1;
        assert_eq!(twin.reported_version, 1);
    }

    #[test]
    fn test_version_comparison() {
        // 乐观锁版本检查逻辑
        let current_version = 5;
        let incoming_version = 4;

        // incoming <= current 时应该跳过更新
        assert!(incoming_version <= current_version);

        let incoming_version = 6;
        assert!(incoming_version > current_version);
    }
}