//! 应用配置

use std::env;

/// 应用配置
#[derive(Debug, Clone)]
pub struct Config {
    /// 服务端口
    pub port: u16,
    /// PostgreSQL 配置
    pub postgres: PostgresConfig,
    /// Redis 配置
    pub redis: RedisConfig,
    /// MQTT 配置
    pub mqtt: MqttConfig,
    /// EMQX 配置
    pub emqx: EmqxConfig,
}

#[derive(Debug, Clone)]
pub struct PostgresConfig {
    pub host: String,
    pub port: u16,
    pub user: String,
    pub password: String,
    pub database: String,
    pub max_connections: u32,
}

#[derive(Debug, Clone)]
pub struct RedisConfig {
    pub host: String,
    pub port: u16,
    pub password: String,
}

#[derive(Debug, Clone)]
pub struct MqttConfig {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
}

#[derive(Debug, Clone)]
pub struct EmqxConfig {
    pub dashboard_url: String,
    pub username: String,
    pub password: String,
}

impl Config {
    /// 从环境变量加载配置
    pub fn from_env() -> Self {
        Self {
            port: env::var("SERVER_PORT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(8000),
            postgres: PostgresConfig {
                host: env::var("POSTGRES_HOST").unwrap_or_else(|_| "localhost".into()),
                port: env::var("POSTGRES_PORT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(5432),
                user: env::var("POSTGRES_USER").unwrap_or_else(|_| "buildroot".into()),
                password: env::var("POSTGRES_PASSWORD").unwrap_or_else(|_| "buildroot123".into()),
                database: env::var("POSTGRES_DB").unwrap_or_else(|_| "buildroot_agent".into()),
                max_connections: env::var("POSTGRES_MAX_CONNECTIONS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(20),
            },
            redis: RedisConfig {
                host: env::var("REDIS_HOST").unwrap_or_else(|_| "localhost".into()),
                port: env::var("REDIS_PORT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(6379),
                password: env::var("REDIS_PASSWORD").unwrap_or_else(|_| "buildroot123".into()),
            },
            mqtt: MqttConfig {
                host: env::var("MQTT_HOST").unwrap_or_else(|_| "localhost".into()),
                port: env::var("MQTT_PORT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(1883),
                username: env::var("MQTT_USERNAME").unwrap_or_default(),
                password: env::var("MQTT_PASSWORD").unwrap_or_default(),
            },
            emqx: EmqxConfig {
                dashboard_url: env::var("EMQX_DASHBOARD_URL")
                    .unwrap_or_else(|_| "http://localhost:18083".into()),
                username: env::var("EMQX_DASHBOARD_USER").unwrap_or_else(|_| "admin".into()),
                password: env::var("EMQX_DASHBOARD_PASSWORD")
                    .unwrap_or_else(|_| "buildroot123".into()),
            },
        }
    }

    /// PostgreSQL 连接字符串
    pub fn postgres_url(&self) -> String {
        format!(
            "postgres://{}:{}@{}:{}/{}",
            self.postgres.user,
            self.postgres.password,
            self.postgres.host,
            self.postgres.port,
            self.postgres.database
        )
    }

    /// Redis 连接 URL
    pub fn redis_url(&self) -> String {
        format!("redis://:{}@{}:{}", self.redis.password, self.redis.host, self.redis.port)
    }
}