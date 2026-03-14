pub mod twin;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use serde_json::json;
use crate::state::AppState;

/// 创建 API 路由
pub fn create_router() -> Router<AppState> {
    Router::new()
        // 根路径
        .route("/", get(root))
        // 健康检查
        .route("/health", get(health))
        // Prometheus 指标
        .route("/metrics", get(metrics_handler))
        // 测试路由
        .route("/test/:id", get(test_handler))
        // WebSocket 端点
        .route("/ws", get(crate::ws::ws_handler))
        // 设备注册
        .route("/api/v1/register", post(twin::register_device))
        // 获取/更新 Twin（同一路径，不同方法）
        .route(
            "/api/v1/devices/:device_id/twin",
            get(twin::get_twin).patch(twin::update_desired),
        )
        // 变更历史
        .route(
            "/api/v1/devices/:device_id/twin/history",
            get(twin::get_history),
        )
        // 列出所有 Twin
        .route("/api/v1/twins", get(twin::list_twins))
        // 设备列表（前端兼容）
        .route("/api/v1/devices", get(twin::list_devices))
        // 批量更新
        .route("/api/v1/twins/batch", post(twin::batch_update))
}

/// 测试 handler
async fn test_handler(
    _state: State<AppState>,
    axum::extract::Path(id): axum::extract::Path<String>,
) -> Json<serde_json::Value> {
    tracing::info!("Test handler called with id: {}", id);
    Json(json!({ "id": id }))
}

/// 根路径
async fn root(_state: State<AppState>) -> Json<serde_json::Value> {
    Json(json!({
        "service": "Buildroot Agent Twin Server",
        "version": "0.1.0",
        "rust": true
    }))
}

/// 健康检查
async fn health(State(state): State<AppState>) -> Json<serde_json::Value> {
    let pg_ok = crate::db::postgres::health_check(&state.db).await;
    let redis_ok = crate::redis::client::health_check(&state.redis).await;
    let mqtt_ok = state.mqtt.is_connected();

    Json(json!({
        "status": if pg_ok && redis_ok && mqtt_ok { "healthy" } else { "degraded" },
        "postgresql": if pg_ok { "connected" } else { "disconnected" },
        "redis": if redis_ok { "connected" } else { "disconnected" },
        "mqtt": if mqtt_ok { "connected" } else { "disconnected" }
    }))
}

/// Prometheus 指标端点
async fn metrics_handler() -> String {
    crate::metrics::gather()
}