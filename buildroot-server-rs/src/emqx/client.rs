//! EMQX REST API 客户端封装

use crate::config::EmqxConfig;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// EMQX REST API 客户端
#[derive(Clone)]
pub struct EmqxClient {
    client: Client,
    config: Arc<EmqxConfig>,
    token: Arc<tokio::sync::RwLock<Option<String>>>,
    authenticator_id: Arc<tokio::sync::RwLock<Option<String>>>,
}

#[derive(Debug, Serialize)]
struct LoginRequest {
    username: String,
    password: String,
}

#[derive(Debug, Deserialize)]
struct LoginResponse {
    token: String,
}

#[derive(Debug, Deserialize)]
struct Authenticator {
    id: String,
}

#[derive(Debug, Serialize)]
struct CreateUserRequest {
    user_id: String,
    password: String,
    is_superuser: bool,
}

#[derive(Debug, Serialize)]
struct UpdateUserRequest {
    password: String,
    is_superuser: bool,
}

impl EmqxClient {
    /// 创建 EMQX 客户端
    pub fn new(config: EmqxConfig) -> Self {
        Self {
            client: Client::new(),
            config: Arc::new(config),
            token: Arc::new(tokio::sync::RwLock::new(None)),
            authenticator_id: Arc::new(tokio::sync::RwLock::new(None)),
        }
    }

    /// 获取认证 token
    async fn get_token(&self) -> anyhow::Result<String> {
        let token_guard = self.token.read().await;
        if let Some(token) = token_guard.as_ref() {
            return Ok(token.clone());
        }
        drop(token_guard);

        // 登录获取新 token
        let url = format!("{}/api/v5/login", self.config.dashboard_url);
        let resp = self
            .client
            .post(&url)
            .json(&LoginRequest {
                username: self.config.username.clone(),
                password: self.config.password.clone(),
            })
            .send()
            .await?;

        let data: LoginResponse = resp.json().await?;
        
        let mut token_guard = self.token.write().await;
        *token_guard = Some(data.token.clone());
        
        Ok(data.token)
    }

    /// 获取认证头
    async fn get_auth_header(&self) -> anyhow::Result<String> {
        let token = self.get_token().await?;
        Ok(format!("Bearer {}", token))
    }

    /// 获取内置数据库认证器 ID
    async fn get_authenticator_id(&self) -> anyhow::Result<String> {
        let guard = self.authenticator_id.read().await;
        if let Some(id) = guard.as_ref() {
            return Ok(id.clone());
        }
        drop(guard);

        let url = format!("{}/api/v5/authentication", self.config.dashboard_url);
        let auth_header = self.get_auth_header().await?;
        
        let resp = self
            .client
            .get(&url)
            .header("Authorization", auth_header)
            .send()
            .await?;

        let authenticators: Vec<Authenticator> = resp.json().await?;

        // 查找内置数据库认证器
        for auth in authenticators {
            if auth.id.contains("built_in_database") {
                let mut guard = self.authenticator_id.write().await;
                *guard = Some(auth.id.clone());
                return Ok(auth.id);
            }
        }

        Err(anyhow::anyhow!("No built_in_database authenticator found"))
    }

    /// 创建设备 MQTT 用户
    pub async fn create_device_user(&self, device_id: &str, password: &str) -> anyhow::Result<bool> {
        let authenticator_id = self.get_authenticator_id().await?;
        let url = format!(
            "{}/api/v5/authentication/{}/users",
            self.config.dashboard_url, authenticator_id
        );
        let auth_header = self.get_auth_header().await?;

        let resp = self
            .client
            .post(&url)
            .header("Authorization", &auth_header)
            .json(&CreateUserRequest {
                user_id: device_id.to_string(),
                password: password.to_string(),
                is_superuser: false,
            })
            .send()
            .await?;

        if resp.status().as_u16() == 409 {
            // 用户已存在，更新密码
            let update_url = format!(
                "{}/api/v5/authentication/{}/users/{}",
                self.config.dashboard_url, authenticator_id, device_id
            );
            let update_resp = self
                .client
                .put(&update_url)
                .header("Authorization", auth_header)
                .json(&UpdateUserRequest {
                    password: password.to_string(),
                    is_superuser: false,
                })
                .send()
                .await?;

            if !update_resp.status().is_success() {
                tracing::warn!("Failed to update user password: {}", update_resp.status());
                return Ok(false);
            }
            return Ok(true);
        }

        if !resp.status().is_success() {
            tracing::warn!("Failed to create user: {}", resp.status());
            return Ok(false);
        }

        Ok(true)
    }

    /// 删除设备 MQTT 用户
    pub async fn delete_device_user(&self, device_id: &str) -> anyhow::Result<bool> {
        let authenticator_id = self.get_authenticator_id().await?;
        let url = format!(
            "{}/api/v5/authentication/{}/users/{}",
            self.config.dashboard_url, authenticator_id, device_id
        );
        let auth_header = self.get_auth_header().await?;

        let resp = self
            .client
            .delete(&url)
            .header("Authorization", auth_header)
            .send()
            .await?;

        if resp.status().as_u16() == 404 {
            return Ok(false);
        }

        if !resp.status().is_success() {
            return Ok(false);
        }

        Ok(true)
    }
}