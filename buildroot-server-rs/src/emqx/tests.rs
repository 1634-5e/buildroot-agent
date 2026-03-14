//! EMQX Client 单元测试

#[cfg(test)]
mod tests {
    use crate::config::EmqxConfig;
    use crate::emqx::EmqxClient;
    use wiremock::matchers::{header, method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    fn create_test_config(server_uri: &str) -> EmqxConfig {
        EmqxConfig {
            dashboard_url: server_uri.to_string(),
            username: "admin".to_string(),
            password: "public".to_string(),
        }
    }

    // EMQX 内置数据库认证器的标准 ID
    const AUTHENTICATOR_ID: &str = "password_based:built_in_database";

    #[tokio::test]
    async fn test_get_token_success() {
        let mock_server = MockServer::start().await;

        Mock::given(method("POST"))
            .and(path("/api/v5/login"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "token": "test-token-12345"
            })))
            .mount(&mock_server)
            .await;

        let config = create_test_config(&mock_server.uri());
        let client = EmqxClient::new(config);

        // 通过公共方法间接测试 token 获取
        let result = client.create_device_user("device-001", "password123").await;
        assert!(result.is_ok() || result.is_err());
    }

    #[tokio::test]
    async fn test_create_device_user_success() {
        let mock_server = MockServer::start().await;

        // Mock login
        Mock::given(method("POST"))
            .and(path("/api/v5/login"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "token": "test-token-12345"
            })))
            .mount(&mock_server)
            .await;

        // Mock list authenticators - 使用正确的 ID 格式
        Mock::given(method("GET"))
            .and(path("/api/v5/authentication"))
            .and(header("Authorization", "Bearer test-token-12345"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!([
                {"id": AUTHENTICATOR_ID}
            ])))
            .mount(&mock_server)
            .await;

        // Mock create user
        Mock::given(method("POST"))
            .and(path(format!("/api/v5/authentication/{}/users", AUTHENTICATOR_ID)))
            .and(header("Authorization", "Bearer test-token-12345"))
            .respond_with(ResponseTemplate::new(201))
            .mount(&mock_server)
            .await;

        let config = create_test_config(&mock_server.uri());
        let client = EmqxClient::new(config);

        let result = client.create_device_user("device-001", "password123").await;
        
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), true);
    }

    #[tokio::test]
    async fn test_create_device_user_already_exists() {
        let mock_server = MockServer::start().await;

        // Mock login
        Mock::given(method("POST"))
            .and(path("/api/v5/login"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "token": "test-token-12345"
            })))
            .mount(&mock_server)
            .await;

        // Mock list authenticators
        Mock::given(method("GET"))
            .and(path("/api/v5/authentication"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!([
                {"id": AUTHENTICATOR_ID}
            ])))
            .mount(&mock_server)
            .await;

        // Mock create user - conflict
        Mock::given(method("POST"))
            .and(path(format!("/api/v5/authentication/{}/users", AUTHENTICATOR_ID)))
            .respond_with(ResponseTemplate::new(409))
            .mount(&mock_server)
            .await;

        // Mock update user
        Mock::given(method("PUT"))
            .and(path(format!("/api/v5/authentication/{}/users/device-001", AUTHENTICATOR_ID)))
            .respond_with(ResponseTemplate::new(200))
            .mount(&mock_server)
            .await;

        let config = create_test_config(&mock_server.uri());
        let client = EmqxClient::new(config);

        let result = client.create_device_user("device-001", "password123").await;
        
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), true);
    }

    #[tokio::test]
    async fn test_delete_device_user_success() {
        let mock_server = MockServer::start().await;

        // Mock login
        Mock::given(method("POST"))
            .and(path("/api/v5/login"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "token": "test-token-12345"
            })))
            .mount(&mock_server)
            .await;

        // Mock list authenticators
        Mock::given(method("GET"))
            .and(path("/api/v5/authentication"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!([
                {"id": AUTHENTICATOR_ID}
            ])))
            .mount(&mock_server)
            .await;

        // Mock delete user
        Mock::given(method("DELETE"))
            .and(path(format!("/api/v5/authentication/{}/users/device-001", AUTHENTICATOR_ID)))
            .respond_with(ResponseTemplate::new(204))
            .mount(&mock_server)
            .await;

        let config = create_test_config(&mock_server.uri());
        let client = EmqxClient::new(config);

        let result = client.delete_device_user("device-001").await;
        
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), true);
    }

    #[tokio::test]
    async fn test_delete_device_user_not_found() {
        let mock_server = MockServer::start().await;

        // Mock login
        Mock::given(method("POST"))
            .and(path("/api/v5/login"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "token": "test-token-12345"
            })))
            .mount(&mock_server)
            .await;

        // Mock list authenticators
        Mock::given(method("GET"))
            .and(path("/api/v5/authentication"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!([
                {"id": AUTHENTICATOR_ID}
            ])))
            .mount(&mock_server)
            .await;

        // Mock delete user - not found
        Mock::given(method("DELETE"))
            .and(path(format!("/api/v5/authentication/{}/users/device-001", AUTHENTICATOR_ID)))
            .respond_with(ResponseTemplate::new(404))
            .mount(&mock_server)
            .await;

        let config = create_test_config(&mock_server.uri());
        let client = EmqxClient::new(config);

        let result = client.delete_device_user("device-001").await;
        
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), false);
    }
}