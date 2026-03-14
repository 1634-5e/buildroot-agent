//! Twin Service 单元测试

#[cfg(test)]
mod tests {
    use crate::models::twin::{DeviceTwin, TwinOverview};
    use serde_json::json;

    #[test]
    fn test_device_twin_new() {
        let twin = DeviceTwin::new("test-device-001");
        assert_eq!(twin.device_id, "test-device-001");
        assert_eq!(twin.desired_version, 0);
        assert_eq!(twin.reported_version, 0);
        assert!(twin.desired.is_object());
        assert!(twin.reported.is_object());
    }

    #[test]
    fn test_twin_overview_delta() {
        let mut twin = DeviceTwin::new("test-device");
        twin.desired = json!({
            "firmware": {"version": "2.0.0"},
            "config": {"interval": 60}
        });
        twin.reported = json!({
            "firmware": {"version": "1.0.0"},
            "config": {"interval": 60}
        });

        let overview = TwinOverview::from(twin);
        
        // Delta 应该只包含 firmware，因为 config 相同
        assert!(overview.delta.is_object());
        let delta = overview.delta.as_object().unwrap();
        assert!(delta.contains_key("firmware"));
        // config 不在 delta 中
        if let Some(delta_obj) = delta.get("firmware").and_then(|v| v.as_object()) {
            assert_eq!(delta_obj.get("version").and_then(|v| v.as_str()), Some("2.0.0"));
        }
    }

    #[test]
    fn test_delta_calculation_all_synced() {
        let mut twin = DeviceTwin::new("synced-device");
        twin.desired = json!({"version": "1.0.0"});
        twin.reported = json!({"version": "1.0.0"});

        let overview = TwinOverview::from(twin);
        assert!(overview.is_synced);
    }

    #[test]
    fn test_delta_calculation_not_synced() {
        let mut twin = DeviceTwin::new("unsynced-device");
        twin.desired = json!({"version": "2.0.0"});
        twin.reported = json!({"version": "1.0.0"});

        let overview = TwinOverview::from(twin);
        assert!(!overview.is_synced);
    }

    #[test]
    fn test_empty_delta_when_reported_missing() {
        let mut twin = DeviceTwin::new("partial-device");
        twin.desired = json!({"firmware": {"version": "2.0.0"}});
        twin.reported = json!({});

        let overview = TwinOverview::from(twin);
        let delta = overview.delta.as_object().unwrap();
        assert!(delta.contains_key("firmware"));
    }

    #[test]
    fn test_nested_delta() {
        let mut twin = DeviceTwin::new("nested-device");
        twin.desired = json!({
            "firmware": {
                "version": "2.0.0",
                "url": "https://example.com/firmware.bin"
            },
            "config": {
                "interval": 60,
                "debug": true
            }
        });
        twin.reported = json!({
            "firmware": {
                "version": "1.0.0"
            },
            "config": {
                "interval": 60
            }
        });

        let overview = TwinOverview::from(twin);
        
        // firmware 整个都应该在 delta 中
        let delta = overview.delta.as_object().unwrap();
        assert!(delta.contains_key("firmware"));
        
        let firmware = delta.get("firmware").unwrap().as_object().unwrap();
        assert_eq!(firmware.get("version").and_then(|v| v.as_str()), Some("2.0.0"));
        assert!(firmware.contains_key("url"));
        
        // config 中只有 debug 在 delta 中，interval 相同
        let config = delta.get("config").unwrap().as_object().unwrap();
        assert_eq!(config.len(), 1);
        assert!(config.contains_key("debug"));
    }
}