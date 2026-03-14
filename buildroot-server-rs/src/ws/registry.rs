//! WebSocket 连接注册表
//!
//! 管理前端 Web Console 连接，支持消息路由到 Agent

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{RwLock, mpsc};
use tracing::{debug, info, warn};

use crate::agent::protocol::Message;

/// WebSocket 连接信息
#[derive(Debug)]
pub struct WebSocketConnection {
    pub console_id: String,
    /// 当前绑定的设备 ID
    pub device_id: Option<String>,
    /// PTY 会话 ID 列表
    pub sessions: Vec<u64>,
    /// 消息发送通道
    pub sender: mpsc::Sender<Message>,
}

/// WebSocket 注册表
#[derive(Debug, Clone)]
pub struct WebSocketRegistry {
    /// console_id -> WebSocketConnection
    connections: Arc<RwLock<HashMap<String, WebSocketConnection>>>,
    /// device_id -> console_ids (设备被哪些控制台订阅)
    device_subscribers: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

impl WebSocketRegistry {
    pub fn new() -> Self {
        Self {
            connections: Arc::new(RwLock::new(HashMap::new())),
            device_subscribers: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    /// 注册 WebSocket 连接
    pub async fn register(&self, conn: WebSocketConnection) {
        let console_id = conn.console_id.clone();
        info!("[WS_REGISTRY] Registering console: {}", console_id);
        
        let mut connections = self.connections.write().await;
        connections.insert(console_id.clone(), conn);
        
        info!("[WS_REGISTRY] Console registered: {} (total: {})", console_id, connections.len());
    }
    
    /// 注销 WebSocket 连接
    pub async fn unregister(&self, console_id: &str) -> Option<WebSocketConnection> {
        let mut connections = self.connections.write().await;
        
        if let Some(conn) = connections.remove(console_id) {
            // 清理设备订阅
            if let Some(ref device_id) = conn.device_id {
                let mut subs = self.device_subscribers.write().await;
                if let Some(console_ids) = subs.get_mut(device_id) {
                    console_ids.retain(|id| id != console_id);
                    if console_ids.is_empty() {
                        subs.remove(device_id);
                    }
                }
            }
            
            info!("[WS_REGISTRY] Console unregistered: {} (total: {})", console_id, connections.len());
            return Some(conn);
        }
        None
    }
    
    /// 绑定控制台到设备
    pub async fn bind_device(&self, console_id: &str, device_id: &str) {
        let mut connections = self.connections.write().await;
        
        if let Some(conn) = connections.get_mut(console_id) {
            conn.device_id = Some(device_id.to_string());
            
            // 添加设备订阅
            let mut subs = self.device_subscribers.write().await;
            subs.entry(device_id.to_string())
                .or_insert_with(Vec::new)
                .push(console_id.to_string());
            
            info!("[WS_REGISTRY] Console {} bound to device {}", console_id, device_id);
        }
    }
    
    /// 添加 PTY 会话
    pub async fn add_session(&self, console_id: &str, session_id: u64) {
        let mut connections = self.connections.write().await;
        
        if let Some(conn) = connections.get_mut(console_id) {
            if !conn.sessions.contains(&session_id) {
                conn.sessions.push(session_id);
                debug!("[WS_REGISTRY] Session {} added to console {}", session_id, console_id);
            }
        }
    }
    
    /// 发送消息到指定控制台
    pub async fn send_to_console(&self, console_id: &str, msg: Message) -> anyhow::Result<()> {
        let connections = self.connections.read().await;
        
        match connections.get(console_id) {
            Some(conn) => {
                conn.sender.send(msg).await?;
                debug!("[WS_REGISTRY] Message sent to console {}", console_id);
                Ok(())
            }
            None => {
                warn!("[WS_REGISTRY] Console not found: {}", console_id);
                Err(anyhow::anyhow!("Console not connected: {}", console_id))
            }
        }
    }
    
    /// 广播消息到订阅设备的所有控制台
    pub async fn broadcast_to_device(&self, device_id: &str, msg: Message) {
        let subs = self.device_subscribers.read().await;
        
        if let Some(console_ids) = subs.get(device_id) {
            let connections = self.connections.read().await;
            
            for console_id in console_ids {
                if let Some(conn) = connections.get(console_id) {
                    if let Err(e) = conn.sender.send(msg.clone()).await {
                        warn!("[WS_REGISTRY] Failed to send to console {}: {}", console_id, e);
                    }
                }
            }
        }
    }
    
    /// 根据会话 ID 找到对应的控制台并发送消息
    pub async fn send_by_session(&self, session_id: u64, msg: Message) -> bool {
        let connections = self.connections.read().await;
        
        for (console_id, conn) in connections.iter() {
            if conn.sessions.contains(&session_id) {
                if let Err(e) = conn.sender.send(msg).await {
                    warn!("[WS_REGISTRY] Failed to send to console {}: {}", console_id, e);
                }
                return true;
            }
        }
        false
    }
}

impl Default for WebSocketRegistry {
    fn default() -> Self {
        Self::new()
    }
}