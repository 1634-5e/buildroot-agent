//! WebSocket 协议 - 请求/响应数据结构

use serde::{Deserialize, Serialize};

/// DEVICE_LIST 请求
#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct DeviceListRequest {
    #[serde(default)]
    pub page: u32,
    #[serde(default = "default_page_size")]
    pub page_size: u32,
}

fn default_page_size() -> u32 { 20 }

/// DEVICE_LIST 响应
#[derive(Debug, Serialize)]
pub struct DeviceListResponse {
    pub devices: Vec<DeviceInfo>,
    pub total_count: usize,
    pub page: u32,
    pub page_size: u32,
}

/// 设备信息（给前端显示用）
#[derive(Debug, Serialize)]
pub struct DeviceInfo {
    pub device_id: String,
    pub name: Option<String>,
    pub device_type: Option<String>,
    pub is_online: bool,
    pub tags: Option<serde_json::Value>,
}

/// DEVICE_UPDATE 请求
#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct DeviceUpdateRequest {
    pub device_id: String,
    pub name: Option<String>,
    pub tags: Option<serde_json::Value>,
}

/// DEVICE_UPDATE 响应
#[derive(Debug, Serialize)]
pub struct DeviceUpdateResponse {
    pub success: bool,
    pub device_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}