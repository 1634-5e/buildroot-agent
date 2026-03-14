//! Agent 连接注册表
//!
//! 管理已连接的 Agent 设备，支持 WebSocket 和 TCP Socket 转发

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{RwLock, mpsc};
use tracing::{debug, info, warn};

use super::protocol::Message;

/// Agent 连接信息
#[derive(Debug, Clone)]
pub struct AgentConnection {
    pub device_id: String,
    pub version: Option<String>,
    pub sender: mpsc::Sender<Message>,
    pub connected_at: chrono::DateTime<chrono::Utc>,
}

/// Agent 注册表
#[derive(Debug, Clone)]
pub struct AgentRegistry {
    /// device_id -> AgentConnection
    agents: Arc<RwLock<HashMap<String, AgentConnection>>>,
}

impl AgentRegistry {
    /// 创建新的注册表
    pub fn new() -> Self {
        Self {
            agents: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    /// 注册 Agent
    pub async fn register(&self, conn: AgentConnection) {
        let device_id = conn.device_id.clone();
        info!("[AGENT_REGISTRY] Registering agent: {}", device_id);
        
        let mut agents = self.agents.write().await;
        
        // 如果已存在，先移除旧连接
        if let Some(old) = agents.insert(device_id.clone(), conn) {
            warn!("[AGENT_REGISTRY] Replaced existing connection for: {}", device_id);
            // 通知旧连接关闭
            let _ = old.sender.send(Message::new_raw(
                super::protocol::MessageType::DeviceDisconnect,
                b"replaced by new connection".to_vec(),
            )).await;
        }
        
        info!("[AGENT_REGISTRY] Agent registered: {} (total: {})", device_id, agents.len());
    }
    
    /// 注销 Agent
    pub async fn unregister(&self, device_id: &str) {
        let mut agents = self.agents.write().await;
        
        if agents.remove(device_id).is_some() {
            info!("[AGENT_REGISTRY] Agent unregistered: {} (total: {})", device_id, agents.len());
        }
    }
    
    /// 检查 Agent 是否在线
    pub async fn is_connected(&self, device_id: &str) -> bool {
        let agents = self.agents.read().await;
        agents.contains_key(device_id)
    }
    
    /// 发送消息到 Agent
    pub async fn send_to_agent(&self, device_id: &str, msg: Message) -> anyhow::Result<()> {
        let agents = self.agents.read().await;
        
        match agents.get(device_id) {
            Some(conn) => {
                conn.sender.send(msg).await?;
                debug!("[AGENT_REGISTRY] Message sent to agent: {}", device_id);
                Ok(())
            }
            None => {
                warn!("[AGENT_REGISTRY] Agent not found: {}", device_id);
                Err(anyhow::anyhow!("Agent not connected: {}", device_id))
            }
        }
    }
    
    /// 获取所有在线设备 ID
    pub async fn get_all_device_ids(&self) -> Vec<String> {
        let agents = self.agents.read().await;
        agents.keys().cloned().collect()
    }
    
    /// 获取在线设备数量
    pub async fn count(&self) -> usize {
        let agents = self.agents.read().await;
        agents.len()
    }
    
    /// 广播消息到所有 Agent
    pub async fn broadcast(&self, msg: Message) {
        let agents = self.agents.read().await;
        
        for (device_id, conn) in agents.iter() {
            if let Err(e) = conn.sender.send(msg.clone()).await {
                warn!("[AGENT_REGISTRY] Failed to broadcast to {}: {}", device_id, e);
            }
        }
    }
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}