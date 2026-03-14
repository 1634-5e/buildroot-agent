//! Redis 客户端

use fred::prelude::*;
use crate::config::Config;
use crate::error::{AppError, Result};

pub type RedisClient = RedisPool;

/// 创建 Redis 连接池
pub async fn create_client(config: &Config) -> Result<RedisClient> {
    tracing::info!("Connecting to Redis: {}:{}", config.redis.host, config.redis.port);
    
    let redis_config = RedisConfig::from_url(&format!(
        "redis://:{}@{}:{}",
        config.redis.password,
        config.redis.host,
        config.redis.port
    )).map_err(|e| AppError::Redis(e.to_string()))?;
    
    let client = RedisPool::new(redis_config, None, None, None, 5)
        .map_err(|e| AppError::Redis(e.to_string()))?;
    
    client.connect();
    client.wait_for_connect().await
        .map_err(|e| AppError::Redis(e.to_string()))?;
    
    tracing::info!("Redis connected");
    
    Ok(client)
}

/// 检查 Redis 连接
pub async fn health_check(client: &RedisClient) -> bool {
    client.ping::<String>().await.is_ok()
}

/// Redis 键值对结果
#[derive(Debug, Clone)]
pub struct TwinCache {
    pub desired: String,
    pub desired_version: String,
    pub reported: String,
    pub reported_version: String,
    pub tags: String,
}