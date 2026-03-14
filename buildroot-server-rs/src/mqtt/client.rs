//! MQTT 客户端封装

use rumqttc::{AsyncClient, Event, Incoming, MqttOptions, QoS};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::broadcast;
use tokio_util::sync::CancellationToken;

/// MQTT 客户端
#[derive(Clone)]
pub struct MqttClient {
    client: AsyncClient,
    connected: Arc<AtomicBool>,
}

impl MqttClient {
    /// 创建 MQTT 客户端并启动后台事件循环
    /// 返回客户端实例和连接状态接收器
    pub fn new(
        host: &str,
        port: u16,
        username: &str,
        password: &str,
        cancel_token: CancellationToken,
    ) -> (Self, broadcast::Receiver<bool>) {
        let mut options = MqttOptions::new("twin-server", host, port);
        
        if !username.is_empty() {
            options.set_credentials(username, password);
        }
        
        options.set_keep_alive(std::time::Duration::from_secs(30));
        options.set_clean_session(true);

        let (client, mut event_loop) = AsyncClient::new(options, 100);
        let connected = Arc::new(AtomicBool::new(false));
        let connected_clone = connected.clone();
        
        // 用于通知连接状态变化
        let (tx, rx) = broadcast::channel::<bool>(1);

        // 后台运行事件循环，支持取消
        tokio::spawn(async move {
            loop {
                tokio::select! {
                    // 收到取消信号，退出循环
                    _ = cancel_token.cancelled() => {
                        tracing::info!("MQTT event loop shutting down...");
                        break;
                    }
                    // 正常事件处理
                    result = event_loop.poll() => {
                        match result {
                            Ok(Event::Incoming(Incoming::ConnAck(_))) => {
                                tracing::info!("MQTT connected");
                                connected_clone.store(true, Ordering::SeqCst);
                                let _ = tx.send(true);
                            }
                            Ok(Event::Incoming(Incoming::Disconnect)) => {
                                tracing::warn!("MQTT disconnected");
                                connected_clone.store(false, Ordering::SeqCst);
                                let _ = tx.send(false);
                            }
                            Err(e) => {
                                tracing::error!("MQTT error: {}", e);
                                connected_clone.store(false, Ordering::SeqCst);
                                tokio::time::sleep(std::time::Duration::from_secs(5)).await;
                            }
                            _ => {}
                        }
                    }
                }
            }
            tracing::info!("MQTT event loop stopped");
        });

        (Self { client, connected }, rx)
    }

    /// 发布消息
    pub async fn publish(&self, topic: &str, payload: &str) -> anyhow::Result<()> {
        self.client
            .publish(topic, QoS::AtLeastOnce, false, payload)
            .await?;
        tracing::debug!("Published to {}: {} bytes", topic, payload.len());
        Ok(())
    }

    /// 发布 JSON 消息
    pub async fn publish_json<T: serde::Serialize>(&self, topic: &str, data: &T) -> anyhow::Result<()> {
        let payload = serde_json::to_string(data)?;
        self.publish(topic, &payload).await
    }

    /// 订阅主题
    pub async fn subscribe(&self, topic: &str) -> anyhow::Result<()> {
        self.client.subscribe(topic, QoS::AtLeastOnce).await?;
        tracing::info!("Subscribed to {}", topic);
        Ok(())
    }

    /// 发布 desired 状态到设备
    pub async fn publish_desired(&self, device_id: &str, desired: &serde_json::Value, version: i64) -> anyhow::Result<()> {
        let topic = format!("twin/{}/desired", device_id);
        let payload = serde_json::json!({
            "desired": desired,
            "$version": version,
        });
        self.publish_json(&topic, &payload).await
    }

    /// 检查连接状态
    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }
}