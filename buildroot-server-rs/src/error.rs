//! 错误类型定义

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

/// 应用错误类型
#[derive(Debug, Error)]
pub enum AppError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),

    #[error("Redis error: {0}")]
    Redis(String),

    #[error("MQTT error: {0}")]
    Mqtt(String),

    #[error("HTTP error: {0}")]
    Http(String),

    #[error("Device not found: {0}")]
    NotFound(String),

    #[error("Invalid request: {0}")]
    BadRequest(String),

    #[error("Internal error: {0}")]
    Internal(String),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            AppError::NotFound(id) => (StatusCode::NOT_FOUND, format!("Device not found: {}", id)),
            AppError::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg.clone()),
            AppError::Database(e) => {
                tracing::error!("Database error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Database error".into())
            }
            AppError::Redis(e) => {
                tracing::error!("Redis error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Cache error".into())
            }
            AppError::Mqtt(e) => {
                tracing::error!("MQTT error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "MQTT error".into())
            }
            AppError::Http(e) => {
                tracing::error!("HTTP error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "HTTP error".into())
            }
            AppError::Internal(e) => {
                tracing::error!("Internal error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal error".into())
            }
        };

        let body = Json(json!({
            "error": message,
            "status": status.as_u16(),
        }));

        (status, body).into_response()
    }
}

/// Result 别名
pub type Result<T> = std::result::Result<T, AppError>;