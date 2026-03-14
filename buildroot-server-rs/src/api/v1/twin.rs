//! Twin API 路由

use axum::{
    extract::{Path, Query, State},
    Json,
};
use serde::Deserialize;

use crate::error::AppError;
use crate::models::twin::{
    BatchUpdate, BatchUpdateResult, ChangeLog, DeviceRegisterRequest, DeviceRegisterResponse,
    TwinOverview, TwinUpdate,
};
use crate::state::AppState;

/// 查询参数：更新者
#[derive(Debug, Deserialize)]
pub struct UpdateByQuery {
    pub updated_by: String,
}

/// 查询参数：分页
#[derive(Debug, Deserialize)]
pub struct ListQuery {
    #[serde(default = "default_limit")]
    pub limit: i64,
    #[serde(default)]
    pub offset: i64,
    pub is_synced: Option<bool>,
}

fn default_limit() -> i64 {
    50
}

/// 查询参数：历史记录
#[derive(Debug, Deserialize)]
pub struct HistoryQuery {
    #[serde(default = "default_history_limit")]
    pub limit: i64,
    #[serde(default)]
    pub change_type: Option<String>,
}

fn default_history_limit() -> i64 {
    100
}

/// 获取设备 Twin
pub async fn get_twin(
    State(state): State<AppState>,
    Path(device_id): Path<String>,
) -> Result<Json<TwinOverview>, AppError> {
    tracing::info!("Getting twin for device: {}", device_id);

    let twin = state
        .twin
        .get_twin_overview(&device_id)
        .await?
        .ok_or_else(|| {
            tracing::warn!("Device not found: {}", device_id);
            AppError::NotFound(device_id.clone())
        })?;

    tracing::info!("Found twin for device: {}", device_id);
    Ok(Json(twin))
}

/// 更新设备 desired
pub async fn update_desired(
    State(state): State<AppState>,
    Path(device_id): Path<String>,
    Query(query): Query<UpdateByQuery>,
    Json(request): Json<TwinUpdate>,
) -> Result<Json<TwinOverview>, AppError> {
    tracing::info!(
        "Updating desired for device: {} by {}",
        device_id,
        query.updated_by
    );

    let twin = state
        .twin
        .update_desired(&device_id, request.desired, &query.updated_by)
        .await?;

    Ok(Json(TwinOverview::from(twin)))
}

/// 获取变更历史
pub async fn get_history(
    State(state): State<AppState>,
    Path(device_id): Path<String>,
    Query(query): Query<HistoryQuery>,
) -> Result<Json<Vec<ChangeLog>>, AppError> {
    tracing::info!("Getting history for device: {}", device_id);

    let history = state
        .twin
        .get_history(&device_id, query.change_type.as_deref(), query.limit)
        .await?;

    Ok(Json(history))
}

/// 列出所有 Twin
pub async fn list_twins(
    State(state): State<AppState>,
    Query(query): Query<ListQuery>,
) -> Result<Json<Vec<TwinOverview>>, AppError> {
    tracing::info!("Listing twins, limit: {}, offset: {}", query.limit, query.offset);

    let twins = state
        .twin
        .list_twins(query.limit, query.offset, query.is_synced)
        .await?;

    Ok(Json(twins))
}

/// 批量更新
pub async fn batch_update(
    State(state): State<AppState>,
    Json(request): Json<BatchUpdate>,
) -> Result<Json<BatchUpdateResult>, AppError> {
    tracing::info!("Batch update requested");

    let device_ids = request.device_ids.unwrap_or_default();
    if device_ids.is_empty() {
        return Err(AppError::BadRequest("device_ids is required".to_string()));
    }

    let result = state
        .twin
        .batch_update(&device_ids, request.desired, "api")
        .await?;

    Ok(Json(result))
}

/// 设备注册
pub async fn register_device(
    State(state): State<AppState>,
    Json(request): Json<DeviceRegisterRequest>,
) -> Result<Json<DeviceRegisterResponse>, AppError> {
    tracing::info!("Registering device");
    let response = state.twin.register_device(request).await?;
    Ok(Json(response))
}