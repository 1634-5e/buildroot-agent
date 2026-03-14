//! WebSocket 处理器 - 处理前端 Web Console 连接

use axum::{
    extract::{
        ws::{Message as WsMessage, WebSocket, WebSocketUpgrade},
        State,
    },
    response::Response,
};
use futures::{SinkExt, StreamExt};
use tokio::sync::mpsc;
use tracing::{debug, error, info, warn};

use crate::state::AppState;
use crate::agent::protocol::{Message, MessageType};
use crate::ws::registry::WebSocketConnection;
use super::protocol::{DeviceListRequest, DeviceListResponse, DeviceInfo, DeviceUpdateRequest, DeviceUpdateResponse};

/// WebSocket 升级处理器
pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> Response {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

/// 处理 WebSocket 连接
async fn handle_socket(socket: WebSocket, state: AppState) {
    let (mut tx, mut rx) = socket.split();
    
    info!("[WS] New WebSocket connection established");
    
    // 生成 console_id
    let console_id = format!("console-{}", uuid::Uuid::new_v4().simple());
    
    // 创建消息发送通道
    let (msg_tx, mut msg_rx) = mpsc::channel::<Message>(32);
    
    // 注册到 WebSocket 注册表
    let ws_conn = WebSocketConnection {
        console_id: console_id.clone(),
        device_id: None,
        sessions: Vec::new(),
        sender: msg_tx,
    };
    state.websockets.register(ws_conn).await;
    
    // 发送欢迎消息
    let welcome = Message::new(MessageType::SystemStatus, serde_json::json!({
        "status": "connected",
        "server": "rust",
        "version": "0.1.0",
        "console_id": console_id
    }));
    if let Err(e) = tx.send(WsMessage::Binary(welcome.encode())).await {
        error!("[WS] Failed to send welcome message: {}", e);
        state.websockets.unregister(&console_id).await;
        return;
    }
    
    // 消息接收任务
    let state_for_recv = state.clone();
    let console_id_for_recv = console_id.clone();
    let recv_task = async move {
        while let Some(msg) = rx.next().await {
            match msg {
                Ok(WsMessage::Binary(data)) => {
                    match Message::decode(&data) {
                        Ok(message) => {
                            debug!("[WS] Received message: {:?}", message.msg_type);
                            
                            // 绑定设备
                            if let Ok(json) = message.json_value() {
                                if let Some(device_id) = json.get("device_id").and_then(|v| v.as_str()) {
                                    state_for_recv.websockets.bind_device(&console_id_for_recv, device_id).await;
                                }
                                // 添加 PTY 会话
                                if let Some(session_id) = json.get("session_id").and_then(|v| v.as_u64()) {
                                    state_for_recv.websockets.add_session(&console_id_for_recv, session_id).await;
                                }
                            }
                            
                            if let Err(e) = handle_message(&state_for_recv, &console_id_for_recv, message).await {
                                error!("[WS] Error handling message: {}", e);
                            }
                        }
                        Err(e) => {
                            warn!("[WS] Failed to decode message: {}", e);
                        }
                    }
                }
                Ok(WsMessage::Text(text)) => {
                    warn!("[WS] Received text message (expected binary): {}", text.len());
                }
                Ok(WsMessage::Close(_)) => {
                    info!("[WS] Client closed connection");
                    break;
                }
                Ok(WsMessage::Ping(_)) => {
                    debug!("[WS] Ping received");
                }
                Ok(_) => {}
                Err(e) => {
                    error!("[WS] WebSocket error: {}", e);
                    break;
                }
            }
        }
    };
    
    // 消息发送任务
    let send_task = async move {
        while let Some(msg) = msg_rx.recv().await {
            if tx.send(WsMessage::Binary(msg.encode())).await.is_err() {
                break;
            }
        }
    };
    
    // 并行运行发送和接收任务
    tokio::select! {
        _ = send_task => {}
        _ = recv_task => {}
    }
    
    // 清理
    info!("[WS] Connection closed: {}", console_id);
    state.websockets.unregister(&console_id).await;
}

/// 处理单条消息
async fn handle_message(
    state: &AppState,
    console_id: &str,
    message: Message,
) -> anyhow::Result<()> {
    match message.msg_type {
        // 服务端处理的消息
        MessageType::DeviceList => {
            handle_device_list(state, console_id, message.payload).await?;
        }
        MessageType::DeviceUpdate => {
            handle_device_update(state, console_id, message.payload).await?;
        }
        MessageType::DeviceDisconnect => {
            // TODO: 实现设备断开逻辑
            warn!("[WS] DeviceDisconnect not implemented yet");
        }
        
        // 需要转发到 Agent 的消息
        MessageType::PtyCreate
        | MessageType::PtyData
        | MessageType::PtyResize
        | MessageType::PtyClose
        | MessageType::FileRequest
        | MessageType::FileListRequest
        | MessageType::FileDownloadRequest
        | MessageType::CmdRequest => {
            handle_forward_to_agent(state, console_id, message).await?;
        }
        
        // 心跳
        MessageType::Heartbeat => {
            debug!("[WS] Heartbeat received");
        }
        
        // 其他消息类型
        _ => {
            debug!("[WS] Unhandled message type: {:?}", message.msg_type);
        }
    }
    
    Ok(())
}

/// 转发消息到 Agent
async fn handle_forward_to_agent(
    state: &AppState,
    _console_id: &str,
    message: Message,
) -> anyhow::Result<()> {
    // 解析 payload 获取 device_id
    let payload: serde_json::Value = serde_json::from_slice(&message.payload)?;
    let device_id = payload.get("device_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("Missing device_id in message"))?;
    
    info!("[WS] Forwarding {:?} to agent: {}", message.msg_type, device_id);
    
    // 检查 Agent 是否在线
    if !state.agents.is_connected(device_id).await {
        warn!("[WS] Agent not connected: {}", device_id);
        
        // 返回错误响应
        let error_resp = Message::new(MessageType::CmdResponse, serde_json::json!({
            "device_id": device_id,
            "error": format!("Agent {} not connected", device_id),
            "hint": "Make sure the device is connected to Rust Server (port 8766)"
        }));
        
        // 通过注册表发送
        state.websockets.send_to_console(_console_id, error_resp).await?;
        return Ok(());
    }
    
    // 转发消息到 Agent
    state.agents.send_to_agent(device_id, message).await?;
    
    Ok(())
}

/// 处理 DEVICE_LIST 请求
async fn handle_device_list(
    state: &AppState,
    console_id: &str,
    payload: Vec<u8>,
) -> anyhow::Result<()> {
    let request: DeviceListRequest = serde_json::from_slice(&payload)?;
    
    info!(
        "[WS] DeviceList request from {}: page={}, page_size={}",
        console_id, request.page, request.page_size
    );
    
    // 从数据库获取设备列表
    let limit = request.page_size as i64;
    let offset = (request.page * request.page_size) as i64;
    let twins = state.twin.list_twins(limit, offset, None).await?;
    
    // 获取在线 Agent 列表
    let online_devices = state.agents.get_all_device_ids().await;
    
    // 转换为 DeviceInfo
    let devices: Vec<DeviceInfo> = twins
        .iter()
        .map(|twin| {
            let tags_obj = twin.tags.as_object();
            let reported_obj = twin.reported.as_object();
            
            DeviceInfo {
                device_id: twin.device_id.clone(),
                name: tags_obj
                    .and_then(|t| t.get("device_name"))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
                device_type: tags_obj
                    .and_then(|t| t.get("device_type"))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
                is_online: online_devices.contains(&twin.device_id) 
                    || reported_obj.map_or(false, |r| !r.is_empty()),
                tags: Some(twin.tags.clone()),
            }
        })
        .collect();
    
    let total_count = devices.len();
    
    let response = DeviceListResponse {
        devices,
        total_count,
        page: request.page,
        page_size: request.page_size,
    };
    
    let msg = Message::new(MessageType::DeviceList, response);
    state.websockets.send_to_console(console_id, msg).await?;
    
    info!("[WS] DeviceList response sent: {} devices", total_count);
    Ok(())
}

/// 处理 DEVICE_UPDATE 请求
async fn handle_device_update(
    state: &AppState,
    console_id: &str,
    payload: Vec<u8>,
) -> anyhow::Result<()> {
    let request: DeviceUpdateRequest = serde_json::from_slice(&payload)?;
    
    info!(
        "[WS] DeviceUpdate request from {}: device_id={}, name={:?}",
        console_id, request.device_id, request.name
    );
    
    // 构建更新数据
    let mut update_tags = serde_json::Map::new();
    if let Some(name) = &request.name {
        update_tags.insert("device_name".to_string(), serde_json::Value::String(name.clone()));
    }
    if let Some(tags) = &request.tags {
        if let Some(obj) = tags.as_object() {
            for (k, v) in obj {
                update_tags.insert(k.clone(), v.clone());
            }
        }
    }
    
    // 更新设备信息
    let result = sqlx::query(
        r#"
        UPDATE device_twins
        SET tags = COALESCE(
            tags || $2::jsonb,
            $2::jsonb
        ),
        updated_at = NOW()
        WHERE device_id = $1
        RETURNING device_id
        "#,
    )
    .bind(&request.device_id)
    .bind(serde_json::Value::Object(update_tags))
    .fetch_optional(&state.db)
    .await;
    
    let response = match result {
        Ok(Some(_)) => DeviceUpdateResponse {
            success: true,
            device_id: request.device_id.clone(),
            message: Some("Device updated successfully".to_string()),
        },
        Ok(None) => DeviceUpdateResponse {
            success: false,
            device_id: request.device_id.clone(),
            message: Some("Device not found".to_string()),
        },
        Err(e) => {
            error!("[WS] Failed to update device: {}", e);
            DeviceUpdateResponse {
                success: false,
                device_id: request.device_id.clone(),
                message: Some(format!("Update failed: {}", e)),
            }
        }
    };
    
    let msg = Message::new(MessageType::DeviceUpdate, response);
    state.websockets.send_to_console(console_id, msg).await?;
    
    Ok(())
}