//! Twin 服务层 - 核心业务逻辑

use fred::interfaces::HashesInterface;
use crate::db::postgres::DbPool;
use crate::emqx::EmqxClient;
use crate::error::{AppError, Result};
use crate::metrics::{
    CACHE_HITS, CACHE_MISSES, DEVICE_REGISTRATIONS_TOTAL, DEVICE_REGISTRATION_ERRORS,
    MQTT_MESSAGES_PUBLISHED, MQTT_PUBLISH_ERRORS, TWIN_GETS_TOTAL, TWIN_UPDATES_TOTAL,
};
use crate::models::twin::{
    BatchUpdateResult, ChangeLog, DeviceRegisterRequest, DeviceRegisterResponse, DeviceTwin,
    TwinOverview,
};
use crate::mqtt::MqttClient;
use crate::redis::client::RedisClient;
use chrono::Utc;
use serde_json::json;
use sqlx::Row;
use std::sync::Arc;
use tracing::instrument;
use uuid::Uuid;

/// Twin 服务
#[derive(Clone)]
pub struct TwinService {
    db: DbPool,
    redis: RedisClient,
    mqtt: MqttClient,
    emqx: EmqxClient,
    mqtt_broker: String,
    mqtt_port: u16,
}

impl TwinService {
    /// 创建服务实例
    pub fn new(db: DbPool, redis: RedisClient, mqtt: MqttClient, emqx: EmqxClient, mqtt_broker: String, mqtt_port: u16) -> Self {
        Self {
            db,
            redis,
            mqtt,
            emqx,
            mqtt_broker,
            mqtt_port,
        }
    }

    /// 获取设备 Twin
    #[instrument(skip(self), fields(device_id = %device_id))]
    pub async fn get_twin(&self, device_id: &str) -> Result<Option<DeviceTwin>> {
        TWIN_GETS_TOTAL.inc_by(1);

        // 1. 尝试从 Redis 获取
        if let Some(cached) = self.get_cached_twin(device_id).await? {
            tracing::info!("Twin found in cache");
            CACHE_HITS.inc_by(1);
            return Ok(Some(cached));
        }
        CACHE_MISSES.inc_by(1);

        // 2. 从 PostgreSQL 加载
        tracing::info!("Querying database for device: {}", device_id);
        let row = sqlx::query(
            r#"
            SELECT device_id, desired::text, desired_version, reported::text, reported_version,
                   tags::text, created_at, updated_at
            FROM device_twins
            WHERE device_id = $1
            "#,
        )
        .bind(device_id)
        .fetch_optional(&self.db)
        .await;

        match row {
            Ok(Some(r)) => {
                tracing::info!("Row found in database");
                let twin = DeviceTwin {
                    device_id: r.get("device_id"),
                    desired: Self::parse_json(r.get("desired")),
                    desired_version: r.get("desired_version"),
                    reported: Self::parse_json(r.get("reported")),
                    reported_version: r.get("reported_version"),
                    tags: Self::parse_json(r.get("tags")),
                    created_at: r.get("created_at"),
                    updated_at: r.get("updated_at"),
                };

                // 写入缓存
                self.cache_twin(&twin).await?;

                Ok(Some(twin))
            }
            Ok(None) => {
                tracing::warn!("No row found for device: {}", device_id);
                Ok(None)
            }
            Err(e) => {
                tracing::error!("Database error: {}", e);
                Err(AppError::Database(e))
            }
        }
    }

    /// 获取 Twin 概览（含 delta）
    pub async fn get_twin_overview(&self, device_id: &str) -> Result<Option<TwinOverview>> {
        let twin = self.get_twin(device_id).await?;
        Ok(twin.map(TwinOverview::from))
    }

    /// 更新期望状态
    #[instrument(skip(self, desired), fields(device_id = %device_id, updated_by = %updated_by))]
    pub async fn update_desired(
        &self,
        device_id: &str,
        desired: serde_json::Value,
        updated_by: &str,
    ) -> Result<DeviceTwin> {
        // 1. 获取当前 Twin（不存在则创建）
        let mut twin = match self.get_twin(device_id).await? {
            Some(t) => t,
            None => {
                self.create_default_twin(device_id).await?;
                DeviceTwin::new(device_id)
            }
        };

        // 2. 合并 desired（部分更新）
        if let (Some(desired_obj), Some(existing_obj)) =
            (desired.as_object(), twin.desired.as_object())
        {
            let mut merged = existing_obj.clone();
            for (k, v) in desired_obj {
                merged.insert(k.clone(), v.clone());
            }
            twin.desired = serde_json::Value::Object(merged);
        } else {
            twin.desired = desired;
        }
        twin.desired_version += 1;

        // 3. 更新 PostgreSQL
        let now = Utc::now();
        sqlx::query(
            r#"
            UPDATE device_twins
            SET desired = $2, desired_version = $3, desired_at = $4, desired_by = $5, updated_at = $6
            WHERE device_id = $1
            "#,
        )
        .bind(device_id)
        .bind(&twin.desired)
        .bind(twin.desired_version)
        .bind(now)
        .bind(updated_by)
        .bind(now)
        .execute(&self.db)
        .await?;

        // 4. 记录变更历史
        self.log_change(device_id, "desired", &twin.desired, updated_by)
            .await?;

        // 5. 更新缓存
        self.cache_twin(&twin).await?;

        // 6. 推送到 MQTT
        if let Err(e) = self.mqtt.publish_desired(&twin.device_id, &twin.desired, twin.desired_version).await {
            tracing::warn!("Failed to publish desired to MQTT: {}", e);
            MQTT_PUBLISH_ERRORS.inc_by(1);
        } else {
            MQTT_MESSAGES_PUBLISHED.inc_by(1);
        }

        TWIN_UPDATES_TOTAL.with_label_values(&["desired"]).inc_by(1);
        Ok(twin)
    }

    /// 更新已报告状态
    pub async fn update_reported(
        &self,
        device_id: &str,
        reported: serde_json::Value,
        version: i64,
    ) -> Result<DeviceTwin> {
        // 1. 获取当前 Twin
        let mut twin = match self.get_twin(device_id).await? {
            Some(t) => t,
            None => return Err(AppError::NotFound(device_id.to_string())),
        };

        // 2. 版本检查（乐观锁）
        if version <= twin.reported_version {
            return Ok(twin);
        }

        // 3. 合并 reported
        if let (Some(reported_obj), Some(existing_obj)) =
            (reported.as_object(), twin.reported.as_object())
        {
            let mut merged = existing_obj.clone();
            for (k, v) in reported_obj {
                merged.insert(k.clone(), v.clone());
            }
            twin.reported = serde_json::Value::Object(merged);
        } else {
            twin.reported = reported;
        }
        twin.reported_version = version;

        // 4. 更新数据库
        let now = Utc::now();
        sqlx::query(
            r#"
            UPDATE device_twins
            SET reported = $2, reported_version = $3, reported_at = $4, updated_at = $4
            WHERE device_id = $1
            "#,
        )
        .bind(device_id)
        .bind(&twin.reported)
        .bind(twin.reported_version)
        .bind(now)
        .execute(&self.db)
        .await?;

        // 5. 记录变更
        self.log_change(device_id, "reported", &twin.reported, "device")
            .await?;

        // 6. 更新缓存
        self.cache_twin(&twin).await?;

        TWIN_UPDATES_TOTAL.with_label_values(&["reported"]).inc_by(1);
        Ok(twin)
    }

    /// 获取变更历史
    pub async fn get_history(
        &self,
        device_id: &str,
        change_type: Option<&str>,
        limit: i64,
    ) -> Result<Vec<ChangeLog>> {
        let rows = match change_type {
            Some(ct) => {
                sqlx::query(
                    r#"
                    SELECT id, device_id, change_type, old_value::text, new_value::text, changed_by, changed_at
                    FROM twin_change_logs
                    WHERE device_id = $1 AND change_type = $2
                    ORDER BY changed_at DESC
                    LIMIT $3
                    "#,
                )
                .bind(device_id)
                .bind(ct)
                .bind(limit)
                .fetch_all(&self.db)
                .await?
            }
            None => {
                sqlx::query(
                    r#"
                    SELECT id, device_id, change_type, old_value::text, new_value::text, changed_by, changed_at
                    FROM twin_change_logs
                    WHERE device_id = $1
                    ORDER BY changed_at DESC
                    LIMIT $2
                    "#,
                )
                .bind(device_id)
                .bind(limit)
                .fetch_all(&self.db)
                .await?
            }
        };

        Ok(rows
            .into_iter()
            .map(|row| ChangeLog {
                id: row.get("id"),
                device_id: row.get("device_id"),
                change_type: row.get("change_type"),
                old_value: Self::parse_json(row.get("old_value")),
                new_value: Self::parse_json(row.get("new_value")),
                changed_by: row.get("changed_by"),
                changed_at: row.get("changed_at"),
            })
            .collect())
    }

    /// 批量更新（并发执行）
    #[instrument(skip(self, desired), fields(device_count = device_ids.len(), updated_by = %updated_by))]
    pub async fn batch_update(
        &self,
        device_ids: &[String],
        desired: serde_json::Value,
        updated_by: &str,
    ) -> Result<BatchUpdateResult> {
        use futures::future::join_all;

        // 并发数限制（通过分批处理）
        const BATCH_SIZE: usize = 10;

        let desired = Arc::new(desired);
        let updated_by = Arc::new(updated_by.to_string());
        let mut updated_ids = Vec::new();
        let mut updated_count = 0u64;

        // 分批处理
        for chunk in device_ids.chunks(BATCH_SIZE) {
            let futures: Vec<_> = chunk
                .iter()
                .map(|device_id| {
                    let service = self.clone();
                    let desired = desired.clone();
                    let updated_by = updated_by.clone();
                    let device_id = device_id.clone();
                    async move {
                        service
                            .update_desired(&device_id, (*desired).clone(), &updated_by)
                            .await
                            .map(|_| device_id)
                    }
                })
                .collect();

            let results = join_all(futures).await;

            for result in results {
                if let Ok(id) = result {
                    updated_count += 1;
                    updated_ids.push(id);
                }
            }
        }

        Ok(BatchUpdateResult {
            updated: updated_count,
            failed: (device_ids.len() as u64) - updated_count,
            device_ids: updated_ids,
        })
    }

    /// 列出所有 Twin（支持分页和过滤）
    pub async fn list_twins(
        &self,
        limit: i64,
        offset: i64,
        is_synced: Option<bool>,
    ) -> Result<Vec<TwinOverview>> {
        let rows = match is_synced {
            Some(_synced) => {
                sqlx::query(
                    r#"
                    SELECT device_id, desired::text, desired_version, reported::text, reported_version,
                           tags::text, created_at, updated_at
                    FROM device_twins
                    ORDER BY updated_at DESC
                    LIMIT $1 OFFSET $2
                    "#,
                )
                .bind(limit)
                .bind(offset)
                .fetch_all(&self.db)
                .await?
            }
            None => {
                sqlx::query(
                    r#"
                    SELECT device_id, desired::text, desired_version, reported::text, reported_version,
                           tags::text, created_at, updated_at
                    FROM device_twins
                    ORDER BY updated_at DESC
                    LIMIT $1 OFFSET $2
                    "#,
                )
                .bind(limit)
                .bind(offset)
                .fetch_all(&self.db)
                .await?
            }
        };

        let twins: Vec<TwinOverview> = rows
            .into_iter()
            .map(|row| {
                let twin = DeviceTwin {
                    device_id: row.get("device_id"),
                    desired: Self::parse_json(row.get("desired")),
                    desired_version: row.get("desired_version"),
                    reported: Self::parse_json(row.get("reported")),
                    reported_version: row.get("reported_version"),
                    tags: Self::parse_json(row.get("tags")),
                    created_at: row.get("created_at"),
                    updated_at: row.get("updated_at"),
                };
                TwinOverview::from(twin)
            })
            .collect();

        // TODO: 如果有 is_synced 过滤，需要在内存中过滤
        // 目前先返回所有，后续可以优化 SQL

        Ok(twins)
    }

    /// 设备注册
    #[instrument(skip(self), fields(device_name = ?request.device_name, device_type = ?request.device_type))]
    pub async fn register_device(&self, request: DeviceRegisterRequest) -> Result<DeviceRegisterResponse> {
        // 1. 确定 device_id
        let device_id = request.device_id.unwrap_or_else(|| {
            format!("device-{}", Uuid::new_v4().to_string().split('-').next().unwrap())
        });

        // 2. 检查是否已存在
        let existing = self.get_twin(&device_id).await?;
        let created = existing.is_none();

        // 3. 生成 MQTT 密码
        let mqtt_password = Self::generate_password(24);
        let mqtt_username = device_id.clone();

        // 4. 创建 EMQX 用户
        match self.emqx.create_device_user(&device_id, &mqtt_password).await {
            Ok(true) => tracing::info!("Created EMQX user: {}", device_id),
            Ok(false) => tracing::warn!("EMQX user already exists or failed: {}", device_id),
            Err(e) => {
                tracing::warn!("Failed to create EMQX user: {}", e);
                DEVICE_REGISTRATION_ERRORS.inc_by(1);
            }
        }

        // 5. 创建 Twin 记录
        if created {
            self.create_device_twin(
                &device_id,
                request.device_name.as_deref(),
                request.device_type.as_deref(),
                request.firmware_version.as_deref(),
                request.hardware_version.as_deref(),
                request.mac_address.as_deref(),
                request.tags,
            )
            .await?;
        }

        DEVICE_REGISTRATIONS_TOTAL.inc_by(1);
        Ok(DeviceRegisterResponse {
            device_id,
            mqtt_username,
            mqtt_password,
            mqtt_broker: self.mqtt_broker.clone(),
            mqtt_port: self.mqtt_port,
            created,
        })
    }

    // ============ 私有辅助方法 ============

    /// 创建默认 Twin
    async fn create_default_twin(&self, device_id: &str) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO device_twins (device_id)
            VALUES ($1)
            ON CONFLICT (device_id) DO NOTHING
            "#,
        )
        .bind(device_id)
        .execute(&self.db)
        .await?;

        Ok(())
    }

    /// 创建设备 Twin 记录（带标签）
    async fn create_device_twin(
        &self,
        device_id: &str,
        device_name: Option<&str>,
        device_type: Option<&str>,
        firmware_version: Option<&str>,
        hardware_version: Option<&str>,
        mac_address: Option<&str>,
        extra_tags: serde_json::Value,
    ) -> Result<()> {
        let mut tags = match extra_tags.as_object() {
            Some(obj) => obj.clone(),
            None => serde_json::Map::new(),
        };

        if let Some(name) = device_name {
            tags.insert("device_name".to_string(), json!(name));
        }
        if let Some(dt) = device_type {
            tags.insert("device_type".to_string(), json!(dt));
        }
        if let Some(fv) = firmware_version {
            tags.insert("firmware_version".to_string(), json!(fv));
        }
        if let Some(hv) = hardware_version {
            tags.insert("hardware_version".to_string(), json!(hv));
        }
        if let Some(mac) = mac_address {
            tags.insert("mac_address".to_string(), json!(mac));
        }

        sqlx::query(
            r#"
            INSERT INTO device_twins (device_id, tags, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            ON CONFLICT (device_id) DO UPDATE
            SET tags = EXCLUDED.tags, updated_at = NOW()
            "#,
        )
        .bind(device_id)
        .bind(serde_json::Value::Object(tags))
        .execute(&self.db)
        .await?;

        Ok(())
    }

    /// 从缓存获取 Twin
    async fn get_cached_twin(&self, device_id: &str) -> Result<Option<DeviceTwin>> {
        let cache_key = format!("twin:{}", device_id);

        let result: std::collections::HashMap<String, String> = self.redis
            .hgetall(&cache_key)
            .await
            .map_err(|e| AppError::Redis(e.to_string()))?;

        if result.is_empty() {
            return Ok(None);
        }

        let desired = result.get("desired").map(|v| v.as_str()).unwrap_or("{}");
        let reported = result.get("reported").map(|v| v.as_str()).unwrap_or("{}");
        let tags = result.get("tags").map(|v| v.as_str()).unwrap_or("{}");

        Ok(Some(DeviceTwin {
            device_id: device_id.to_string(),
            desired: serde_json::from_str(desired).unwrap_or(json!({})),
            desired_version: result.get("desired_version")
                .and_then(|v: &String| v.parse().ok())
                .unwrap_or(0),
            reported: serde_json::from_str(reported).unwrap_or(json!({})),
            reported_version: result.get("reported_version")
                .and_then(|v: &String| v.parse().ok())
                .unwrap_or(0),
            tags: serde_json::from_str(tags).unwrap_or(json!({})),
            created_at: None,
            updated_at: None,
        }))
    }

    /// 写入缓存
    async fn cache_twin(&self, twin: &DeviceTwin) -> Result<()> {
        use std::collections::BTreeMap;
        
        let cache_key = format!("twin:{}", twin.device_id);

        // fred 9.x 使用 BTreeMap 构造 RedisMap
        let mut map: BTreeMap<_, _> = BTreeMap::new();
        map.insert("desired", twin.desired.to_string());
        map.insert("desired_version", twin.desired_version.to_string());
        map.insert("reported", twin.reported.to_string());
        map.insert("reported_version", twin.reported_version.to_string());
        map.insert("tags", twin.tags.to_string());

        self.redis
            .hset::<(), _, _>(&cache_key, map)
            .await
            .map_err(|e| AppError::Redis(e.to_string()))?;

        Ok(())
    }

    /// 记录变更历史
    async fn log_change(
        &self,
        device_id: &str,
        change_type: &str,
        new_value: &serde_json::Value,
        changed_by: &str,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO twin_change_logs (device_id, change_type, old_value, new_value, changed_by)
            VALUES ($1, $2, '{}'::jsonb, $3, $4)
            "#,
        )
        .bind(device_id)
        .bind(change_type)
        .bind(new_value)
        .bind(changed_by)
        .execute(&self.db)
        .await?;

        Ok(())
    }

    /// 解析 JSON 字段
    fn parse_json(value: Option<String>) -> serde_json::Value {
        match value {
            Some(s) if !s.is_empty() => {
                serde_json::from_str(&s).unwrap_or_else(|_| json!({}))
            }
            _ => json!({}),
        }
    }

    /// 生成随机密码
    fn generate_password(len: usize) -> String {
        use rand::Rng;
        const CHARSET: &[u8] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        let mut rng = rand::thread_rng();
        (0..len)
            .map(|_| {
                let idx = rng.gen_range(0..CHARSET.len());
                CHARSET[idx] as char
            })
            .collect()
    }
}