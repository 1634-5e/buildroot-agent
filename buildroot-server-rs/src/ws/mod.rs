//! WebSocket 模块 - 前端 Web Console 连接处理

mod protocol;
mod handler;
pub mod registry;

pub use handler::ws_handler;
pub use registry::WebSocketRegistry;