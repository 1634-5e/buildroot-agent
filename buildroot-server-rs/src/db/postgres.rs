//! PostgreSQL 连接池

use sqlx::postgres::{PgPoolOptions, PgPool};
use crate::config::Config;
use crate::error::Result;

pub type DbPool = PgPool;

/// 创建 PostgreSQL 连接池
pub async fn create_pool(config: &Config) -> Result<DbPool> {
    let url = config.postgres_url();
    
    tracing::info!("Connecting to PostgreSQL: {}:{}", config.postgres.host, config.postgres.port);
    
    let pool = PgPoolOptions::new()
        .max_connections(config.postgres.max_connections)
        .connect(&url)
        .await?;
    
    tracing::info!("PostgreSQL connected, max_connections: {}", config.postgres.max_connections);
    
    Ok(pool)
}

/// 检查数据库连接
pub async fn health_check(pool: &DbPool) -> bool {
    sqlx::query("SELECT 1")
        .execute(pool)
        .await
        .is_ok()
}