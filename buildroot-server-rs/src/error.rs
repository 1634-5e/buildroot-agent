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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;

    #[test]
    fn test_error_display() {
        let err = AppError::NotFound("device-001".to_string());
        assert_eq!(format!("{}", err), "Device not found: device-001");

        let err = AppError::BadRequest("invalid input".to_string());
        assert_eq!(format!("{}", err), "Invalid request: invalid input");

        let err = AppError::Redis("connection refused".to_string());
        assert_eq!(format!("{}", err), "Redis error: connection refused");
    }

    #[test]
    fn test_error_from_sqlx() {
        let sqlx_err = sqlx::Error::RowNotFound;
        let app_err: AppError = sqlx_err.into();
        
        match app_err {
            AppError::Database(_) => {}
            _ => panic!("Expected Database variant"),
        }
    }

    #[test]
    fn test_not_found_status_code() {
        let err = AppError::NotFound("device-001".to_string());
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }

    #[test]
    fn test_bad_request_status_code() {
        let err = AppError::BadRequest("missing field".to_string());
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    }

    #[test]
    fn test_database_error_status_code() {
        let err = AppError::Database(sqlx::Error::RowNotFound);
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
    }

    #[test]
    fn test_redis_error_status_code() {
        let err = AppError::Redis("connection failed".to_string());
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
    }

    #[test]
    fn test_mqtt_error_status_code() {
        let err = AppError::Mqtt("broker unreachable".to_string());
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
    }

    #[test]
    fn test_http_error_status_code() {
        let err = AppError::Http("timeout".to_string());
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
    }

    #[test]
    fn test_internal_error_status_code() {
        let err = AppError::Internal("unexpected state".to_string());
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
    }
}