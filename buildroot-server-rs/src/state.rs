//! 应用状态

use crate::agent::AgentRegistry;
use crate::config::Config;
use crate::db::postgres::DbPool;
use crate::emqx::EmqxClient;
use crate::mqtt::MqttClient;
use crate::redis::client::RedisClient;
use crate::twin::TwinService;
use crate::ws::WebSocketRegistry;
use std::sync::Arc;
use tokio_util::sync::CancellationToken;

/// 应用共享状态
#[derive(Clone)]
pub struct AppState {
    /// 配置
    pub config: Arc<Config>,
    /// PostgreSQL 连接池
    pub db: DbPool,
    /// Redis 客户端
    pub redis: RedisClient,
    /// MQTT 客户端
    pub mqtt: MqttClient,
    /// EMQX 客户端
    pub emqx: EmqxClient,
    /// Twin 服务
    pub twin: TwinService,
    /// Agent 连接注册表
    pub agents: AgentRegistry,
    /// WebSocket 连接注册表
    pub websockets: WebSocketRegistry,
    /// 取消令牌（优雅关闭）
    pub cancel_token: CancellationToken,
}

impl AppState {
    pub fn new(
        config: Config,
        db: DbPool,
        redis: RedisClient,
        mqtt: MqttClient,
        emqx: EmqxClient,
        cancel_token: CancellationToken,
    ) -> Self {
        let twin = TwinService::new(
            db.clone(),
            redis.clone(),
            mqtt.clone(),
            emqx.clone(),
            config.mqtt.host.clone(),
            config.mqtt.port,
        );
        let agents = AgentRegistry::new();
        let websockets = WebSocketRegistry::new();
        Self {
            config: Arc::new(config),
            db,
            redis,
            mqtt,
            emqx,
            twin,
            agents,
            websockets,
            cancel_token,
        }
    }
}