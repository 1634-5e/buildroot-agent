//! Agent 二进制协议
//!
//! 消息格式: [type: 1 byte][length: 2 bytes BE][json payload]

use serde::{de::DeserializeOwned, Serialize};
use anyhow::{anyhow, Result};

/// 消息类型定义（与 Python Server 兼容）
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MessageType {
    // 系统
    Heartbeat = 0x01,
    SystemStatus = 0x02,
    LogUpload = 0x03,
    ScriptRecv = 0x04,
    ScriptResult = 0x05,
    
    // PTY
    PtyCreate = 0x10,
    PtyData = 0x11,
    PtyResize = 0x12,
    PtyClose = 0x13,
    
    // 文件
    FileRequest = 0x20,
    FileData = 0x21,
    FileListRequest = 0x22,
    FileListResponse = 0x23,
    DownloadPackage = 0x24,
    FileDownloadRequest = 0x25,
    FileDownloadData = 0x26,
    
    // 命令
    CmdRequest = 0x30,
    CmdResponse = 0x31,
    
    // 设备
    DeviceList = 0x50,
    DeviceDisconnect = 0x51,
    DeviceUpdate = 0x52,
    
    // 注册
    Register = 0xF0,
    RegisterResult = 0xF1,
    
    // 固件更新
    UpdateCheck = 0x60,
    UpdateInfo = 0x61,
    UpdateDownload = 0x62,
    UpdateProgress = 0x63,
    UpdateComplete = 0x65,
    UpdateError = 0x66,
    UpdateRollback = 0x67,
    UpdateRequestApproval = 0x68,
    UpdateDownloadReady = 0x69,
    UpdateApproveInstall = 0x6A,
    UpdateDeny = 0x6B,
    UpdateApproveDownload = 0x6C,
    
    // Ping
    PingStatus = 0x70,
}

impl TryFrom<u8> for MessageType {
    type Error = anyhow::Error;
    
    fn try_from(value: u8) -> Result<Self> {
        match value {
            0x01 => Ok(MessageType::Heartbeat),
            0x02 => Ok(MessageType::SystemStatus),
            0x03 => Ok(MessageType::LogUpload),
            0x04 => Ok(MessageType::ScriptRecv),
            0x05 => Ok(MessageType::ScriptResult),
            0x10 => Ok(MessageType::PtyCreate),
            0x11 => Ok(MessageType::PtyData),
            0x12 => Ok(MessageType::PtyResize),
            0x13 => Ok(MessageType::PtyClose),
            0x20 => Ok(MessageType::FileRequest),
            0x21 => Ok(MessageType::FileData),
            0x22 => Ok(MessageType::FileListRequest),
            0x23 => Ok(MessageType::FileListResponse),
            0x24 => Ok(MessageType::DownloadPackage),
            0x25 => Ok(MessageType::FileDownloadRequest),
            0x26 => Ok(MessageType::FileDownloadData),
            0x30 => Ok(MessageType::CmdRequest),
            0x31 => Ok(MessageType::CmdResponse),
            0x50 => Ok(MessageType::DeviceList),
            0x51 => Ok(MessageType::DeviceDisconnect),
            0x52 => Ok(MessageType::DeviceUpdate),
            0xF0 => Ok(MessageType::Register),
            0xF1 => Ok(MessageType::RegisterResult),
            0x60 => Ok(MessageType::UpdateCheck),
            0x61 => Ok(MessageType::UpdateInfo),
            0x62 => Ok(MessageType::UpdateDownload),
            0x63 => Ok(MessageType::UpdateProgress),
            0x65 => Ok(MessageType::UpdateComplete),
            0x66 => Ok(MessageType::UpdateError),
            0x67 => Ok(MessageType::UpdateRollback),
            0x68 => Ok(MessageType::UpdateRequestApproval),
            0x69 => Ok(MessageType::UpdateDownloadReady),
            0x6A => Ok(MessageType::UpdateApproveInstall),
            0x6B => Ok(MessageType::UpdateDeny),
            0x6C => Ok(MessageType::UpdateApproveDownload),
            0x70 => Ok(MessageType::PingStatus),
            _ => Err(anyhow!("Unknown message type: 0x{:02X}", value)),
        }
    }
}

/// Agent 消息
#[derive(Debug, Clone)]
pub struct Message {
    pub msg_type: MessageType,
    pub payload: Vec<u8>,
}

impl Message {
    /// 创建新消息（从 JSON value）
    pub fn new(msg_type: MessageType, payload: impl Serialize) -> Self {
        let payload = serde_json::to_vec(&payload).unwrap_or_default();
        Self { msg_type, payload }
    }
    
    /// 创建原始消息（payload 已经是 bytes）
    pub fn new_raw(msg_type: MessageType, payload: Vec<u8>) -> Self {
        Self { msg_type, payload }
    }
    
    /// 编码为二进制格式
    /// [type: 1 byte][length: 2 bytes BE][json payload]
    pub fn encode(&self) -> Vec<u8> {
        let len = self.payload.len() as u16;
        let mut buf = Vec::with_capacity(3 + self.payload.len());
        buf.push(self.msg_type as u8);
        buf.extend_from_slice(&len.to_be_bytes());
        buf.extend_from_slice(&self.payload);
        buf
    }
    
    /// 从二进制解码
    pub fn decode(data: &[u8]) -> Result<Self> {
        if data.len() < 3 {
            return Err(anyhow!("Message too short: {} bytes", data.len()));
        }
        
        let msg_type = MessageType::try_from(data[0])?;
        let len = u16::from_be_bytes([data[1], data[2]]) as usize;
        
        if data.len() < 3 + len {
            return Err(anyhow!("Incomplete message: expected {} bytes, got {}", 3 + len, data.len()));
        }
        
        let payload = data[3..3 + len].to_vec();
        Ok(Self { msg_type, payload })
    }
    
    /// 解析 JSON payload
    pub fn parse_json<T: DeserializeOwned>(&self) -> Result<T> {
        serde_json::from_slice(&self.payload).map_err(|e| anyhow!("Failed to parse JSON: {}", e))
    }
    
    /// 获取 JSON Value
    pub fn json_value(&self) -> Result<serde_json::Value> {
        serde_json::from_slice(&self.payload).map_err(|e| anyhow!("Failed to parse JSON: {}", e))
    }
}

/// 注册请求
#[derive(Debug, Clone, serde::Deserialize)]
pub struct RegisterRequest {
    pub device_id: String,
    pub version: Option<String>,
}

/// 注册响应
#[derive(Debug, Clone, serde::Serialize)]
pub struct RegisterResult {
    pub success: bool,
    pub device_id: String,
    pub message: Option<String>,
}

/// PTY 创建请求
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct PtyCreateRequest {
    pub session_id: u64,
    pub rows: Option<u16>,
    pub cols: Option<u16>,
}

/// PTY 数据
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct PtyData {
    pub session_id: u64,
    pub data: String,  // base64 encoded
}

/// PTY 调整大小
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct PtyResize {
    pub session_id: u64,
    pub rows: u16,
    pub cols: u16,
}

/// PTY 关闭
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct PtyClose {
    pub session_id: u64,
    pub reason: Option<String>,
}

/// 命令请求
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct CmdRequest {
    pub request_id: String,
    pub cmd: String,
    pub args: Option<Vec<String>>,
    pub timeout: Option<u64>,
}

/// 命令响应
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct CmdResponse {
    pub request_id: String,
    pub status: String,
    pub exit_code: Option<i32>,
    pub stdout: Option<String>,
    pub stderr: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_message_encode_decode() {
        let msg = Message::new(MessageType::Register, serde_json::json!({
            "device_id": "test-device-001",
            "version": "1.0.0"
        }));
        
        let encoded = msg.encode();
        assert!(encoded.len() >= 3);
        assert_eq!(encoded[0], 0xF0);
        
        let decoded = Message::decode(&encoded).unwrap();
        assert_eq!(decoded.msg_type, MessageType::Register);
        
        let req: RegisterRequest = decoded.parse_json().unwrap();
        assert_eq!(req.device_id, "test-device-001");
    }
    
    #[test]
    fn test_message_type_conversion() {
        assert_eq!(MessageType::try_from(0x11).unwrap(), MessageType::PtyData);
        assert_eq!(MessageType::try_from(0xFF).is_ok(), false);
    }
}