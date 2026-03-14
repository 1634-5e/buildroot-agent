//! Agent 连接管理模块
//!
//! 处理 Agent 设备通过 TCP Socket 连接到 Server

mod registry;
mod handler;
pub mod protocol;

pub use registry::AgentRegistry;
pub use handler::run_agent_server;
pub use protocol::{Message, MessageType};