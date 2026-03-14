//! Buildroot Agent Twin Server - 入口

use std::net::SocketAddr;
use tokio_util::sync::CancellationToken;
use tower_http::cors::{Any, CorsLayer};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use buildroot_server::api::v1::create_router;
use buildroot_server::config::Config;
use buildroot_server::db::postgres::create_pool;
use buildroot_server::emqx::EmqxClient;
use buildroot_server::metrics::{self, MQTT_CONNECTED};
use buildroot_server::mqtt::MqttClient;
use buildroot_server::redis::client::create_client;
use buildroot_server::state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 加载 .env
    dotenvy::dotenv().ok();
    
    // 日志初始化
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::new(
                std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
            ),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();
    
    // 初始化 Prometheus 指标
    metrics::init_metrics();
    tracing::info!("Starting Buildroot Agent Twin Server (Rust)...");
    
    // 加载配置
    let config = Config::from_env();
    tracing::info!("Config loaded, listening on port {}", config.port);
    
    // 创建取消令牌
    let cancel_token = CancellationToken::new();
    
    // 连接 PostgreSQL
    let db = create_pool(&config).await?;
    
    // 连接 Redis
    let redis = create_client(&config).await?;
    
    // 创建 MQTT 客户端
    let (mqtt, mut mqtt_status) = MqttClient::new(
        &config.mqtt.host,
        config.mqtt.port,
        &config.mqtt.username,
        &config.mqtt.password,
        cancel_token.clone(),
    );
    
    // 等待 MQTT 连接（带超时）
    match tokio::time::timeout(
        std::time::Duration::from_secs(5),
        mqtt_status.recv(),
    )
    .await
    {
        Ok(Ok(true)) => {
            tracing::info!("MQTT connected successfully");
            MQTT_CONNECTED.set(1);
        }
        Ok(Ok(false)) => {
            tracing::warn!("MQTT disconnected during startup");
            MQTT_CONNECTED.set(0);
        }
        Ok(Err(_)) => {
            tracing::warn!("MQTT status channel closed");
            MQTT_CONNECTED.set(0);
        }
        Err(_) => {
            tracing::warn!("MQTT connection timeout, continuing anyway");
            MQTT_CONNECTED.set(0);
        }
    }
    
    // 创建 EMQX 客户端
    let emqx = EmqxClient::new(config.emqx.clone());
    
    // 创建应用状态
    let state = AppState::new(config.clone(), db, redis, mqtt, emqx, cancel_token.clone());
    
    // CORS 中间件
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);
    
    // 创建路由 - 先 with_state 再 layer
    let app = create_router()
        .with_state(state)
        .layer(cors);
    
    // 启动服务
    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    tracing::info!("Server listening on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(addr).await?;
    
    // 优雅关闭：监听 Ctrl+C
    let shutdown_token = cancel_token.clone();
    tokio::spawn(async move {
        tokio::signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
        tracing::info!("Received shutdown signal, gracefully shutting down...");
        shutdown_token.cancel();
    });
    
    // 运行服务，带优雅关闭
    axum::serve(listener, app)
        .with_graceful_shutdown(async move {
            cancel_token.cancelled().await;
            tracing::info!("HTTP server shutdown initiated");
        })
        .await?;
    
    tracing::info!("Server stopped");
    Ok(())
}