//! Agent TCP Socket 处理器
//!
//! 监听 TCP 连接，处理 Agent 设备注册和消息

use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::{TcpListener, TcpStream};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::mpsc;
use tracing::{debug, error, info, warn};

use super::protocol::{Message, MessageType, RegisterRequest, RegisterResult};
use super::registry::{AgentRegistry, AgentConnection};
use crate::ws::WebSocketRegistry;

/// Agent 服务端口（与 Python Server 兼容）
pub const AGENT_PORT: u16 = 8766;

/// 运行 Agent TCP Server
pub async fn run_agent_server(
    registry: AgentRegistry,
    ws_registry: Arc<WebSocketRegistry>,
) -> anyhow::Result<()> {
    let addr = SocketAddr::from(([0, 0, 0, 0], AGENT_PORT));
    let listener = TcpListener::bind(addr).await?;
    
    info!("[AGENT] TCP Server listening on {}", addr);
    
    loop {
        let (socket, addr) = listener.accept().await?;
        let registry = registry.clone();
        let ws_registry = ws_registry.clone();
        
        tokio::spawn(async move {
            if let Err(e) = handle_agent_connection(socket, addr, registry, ws_registry).await {
                error!("[AGENT] Connection error from {}: {}", addr, e);
            }
        });
    }
}

/// 处理单个 Agent 连接
async fn handle_agent_connection(
    mut socket: TcpStream,
    addr: SocketAddr,
    registry: AgentRegistry,
    ws_registry: Arc<WebSocketRegistry>,
) -> anyhow::Result<()> {
    info!("[AGENT] New connection from {}", addr);
    
    let mut device_id: Option<String> = None;
    let mut registered = false;
    
    // 创建消息发送通道
    let (tx, mut rx) = mpsc::channel::<Message>(32);
    
    loop {
        // 读取消息头 (type: 1 byte, length: 2 bytes)
        let mut header = [0u8; 3];
        
        // 使用 tokio::select! 同时处理读取和发送
        tokio::select! {
            // 从 Agent 读取消息
            read_result = socket.read_exact(&mut header) => {
                match read_result {
                    Ok(_) => {}
                    Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                        info!("[AGENT] Connection closed by {}", addr);
                        break;
                    }
                    Err(e) => {
                        error!("[AGENT] Read error from {}: {}", addr, e);
                        break;
                    }
                }
                
                let msg_type_byte = header[0];
                let msg_len = u16::from_be_bytes([header[1], header[2]]) as usize;
                
                debug!(
                    "[AGENT] Received header: type=0x{:02X}, len={}",
                    msg_type_byte, msg_len
                );
                
                // 读取 payload
                let mut payload = vec![0u8; msg_len];
                if msg_len > 0 {
                    socket.read_exact(&mut payload).await?;
                }
                
                // 处理消息
                if msg_type_byte == MessageType::Register as u8 {
                    // 注册消息
                    match handle_register(&payload, &mut device_id, &registry, tx.clone()).await {
                        Ok(id) => {
                            registered = true;
                            info!("[AGENT] Device registered: {} from {}", id, addr);
                            
                            // 发送注册成功响应
                            let result = RegisterResult {
                                success: true,
                                device_id: id.clone(),
                                message: Some("Registered successfully".to_string()),
                            };
                            let msg = Message::new(MessageType::RegisterResult, result);
                            socket.write_all(&msg.encode()).await?;
                        }
                        Err(e) => {
                            warn!("[AGENT] Registration failed from {}: {}", addr, e);
                            
                            let result = RegisterResult {
                                success: false,
                                device_id: "".to_string(),
                                message: Some(e.to_string()),
                            };
                            let msg = Message::new(MessageType::RegisterResult, result);
                            socket.write_all(&msg.encode()).await?;
                        }
                    }
                } else if registered {
                    // 已注册，处理其他消息
                    if let Some(ref did) = device_id {
                        if let Ok(msg_type) = MessageType::try_from(msg_type_byte) {
                            handle_agent_message(&registry, &ws_registry, did, msg_type, &payload).await;
                        }
                    }
                } else {
                    warn!("[AGENT] Received message before registration from {}", addr);
                }
            }
            
            // 发送消息到 Agent
            Some(msg) = rx.recv() => {
                if let Err(e) = socket.write_all(&msg.encode()).await {
                    error!("[AGENT] Write error to {}: {}", addr, e);
                    break;
                }
            }
        }
    }
    
    // 清理连接
    if let Some(ref did) = device_id {
        registry.unregister(did).await;
        info!("[AGENT] Device disconnected: {}", did);
    }
    
    Ok(())
}

/// 处理注册消息
async fn handle_register(
    payload: &[u8],
    device_id: &mut Option<String>,
    registry: &AgentRegistry,
    sender: mpsc::Sender<Message>,
) -> anyhow::Result<String> {
    let req: RegisterRequest = serde_json::from_slice(payload)?;
    let did = req.device_id.clone();
    
    info!("[AGENT] Register request: device_id={}, version={:?}", did, req.version);
    
    // 创建连接信息
    let conn = AgentConnection {
        device_id: did.clone(),
        version: req.version,
        sender,
        connected_at: chrono::Utc::now(),
    };
    
    // 注册
    registry.register(conn).await;
    
    *device_id = Some(did.clone());
    Ok(did)
}

/// 处理 Agent 发来的消息，转发到 WebSocket
async fn handle_agent_message(
    _registry: &AgentRegistry,
    ws_registry: &Arc<WebSocketRegistry>,
    device_id: &str,
    msg_type: MessageType,
    payload: &[u8],
) {
    match msg_type {
        MessageType::Heartbeat => {
            debug!("[AGENT] Heartbeat from {}", device_id);
        }
        
        MessageType::PtyData => {
            // PTY 数据，转发到对应的 WebSocket
            if let Ok(json) = serde_json::from_slice::<serde_json::Value>(payload) {
                if let Some(session_id) = json.get("session_id").and_then(|v| v.as_u64()) {
                    let msg = Message::new_raw(msg_type, payload.to_vec());
                    if ws_registry.send_by_session(session_id, msg).await {
                        debug!("[AGENT] PtyData forwarded to session {}", session_id);
                    } else {
                        warn!("[AGENT] No WebSocket found for session {}", session_id);
                    }
                }
            }
        }
        
        MessageType::CmdResponse => {
            // 命令响应，根据 session_id 转发
            if let Ok(json) = serde_json::from_slice::<serde_json::Value>(payload) {
                let session_id = json.get("session_id").and_then(|v| v.as_u64());
                
                let msg = Message::new_raw(msg_type, payload.to_vec());
                
                // 优先用 session_id
                if let Some(sid) = session_id {
                    if ws_registry.send_by_session(sid, msg).await {
                        debug!("[AGENT] CmdResponse forwarded to session {}", sid);
                    }
                }
            }
        }
        
        MessageType::FileListResponse | MessageType::FileData | MessageType::DownloadPackage => {
            // 文件操作响应，直接广播到设备订阅的所有控制台
            let msg = Message::new_raw(msg_type, payload.to_vec());
            ws_registry.broadcast_to_device(device_id, msg).await;
            debug!("[AGENT] {:?} broadcast to device {}", msg_type, device_id);
        }
        
        _ => {
            debug!("[AGENT] Unhandled message type {:?} from {}", msg_type, device_id);
        }
    }
}