//! Prometheus 指标定义

use lazy_static::lazy_static;
use prometheus::{Histogram, HistogramOpts, IntCounter, IntCounterVec, IntGauge, IntGaugeVec, Opts, Registry};

lazy_static! {
    /// 全局 Registry
    pub static ref REGISTRY: Registry = Registry::new();

    // ============ 设备指标 ============

    /// 设备总数
    pub static ref DEVICES_TOTAL: IntGauge = IntGauge::new(
        "buildroot_devices_total",
        "Total number of registered devices"
    ).unwrap();

    /// 设备在线状态
    pub static ref DEVICES_ONLINE: IntGaugeVec = IntGaugeVec::new(
        Opts::new("buildroot_device_online", "Device online status (1=online, 0=offline)"),
        &["device_id"]
    ).unwrap();

    /// 设备同步状态
    pub static ref DEVICES_SYNCED: IntGaugeVec = IntGaugeVec::new(
        Opts::new("buildroot_device_synced", "Device sync status (1=synced, 0=not synced)"),
        &["device_id"]
    ).unwrap();

    // ============ API 指标 ============

    /// HTTP 请求总数
    pub static ref HTTP_REQUESTS_TOTAL: IntCounterVec = IntCounterVec::new(
        Opts::new("buildroot_http_requests_total", "Total number of HTTP requests"),
        &["method", "path", "status"]
    ).unwrap();

    /// HTTP 请求延迟
    pub static ref HTTP_REQUEST_DURATION: Histogram = Histogram::with_opts(
        HistogramOpts::new(
            "buildroot_http_request_duration_seconds",
            "HTTP request duration in seconds"
        )
        .buckets(vec![0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
    ).unwrap();

    /// 活跃请求数
    pub static ref HTTP_REQUESTS_IN_PROGRESS: IntGauge = IntGauge::new(
        "buildroot_http_requests_in_progress",
        "Number of HTTP requests currently being processed"
    ).unwrap();

    // ============ MQTT 指标 ============

    /// MQTT 连接状态
    pub static ref MQTT_CONNECTED: IntGauge = IntGauge::new(
        "buildroot_mqtt_connected",
        "MQTT connection status (1=connected, 0=disconnected)"
    ).unwrap();

    /// MQTT 消息发布总数
    pub static ref MQTT_MESSAGES_PUBLISHED: IntCounter = IntCounter::new(
        "buildroot_mqtt_messages_published_total",
        "Total number of MQTT messages published"
    ).unwrap();

    /// MQTT 消息接收总数
    pub static ref MQTT_MESSAGES_RECEIVED: IntCounter = IntCounter::new(
        "buildroot_mqtt_messages_received_total",
        "Total number of MQTT messages received"
    ).unwrap();

    /// MQTT 发布失败数
    pub static ref MQTT_PUBLISH_ERRORS: IntCounter = IntCounter::new(
        "buildroot_mqtt_publish_errors_total",
        "Total number of MQTT publish errors"
    ).unwrap();

    // ============ Twin 操作指标 ============

    /// Twin 更新总数
    pub static ref TWIN_UPDATES_TOTAL: IntCounterVec = IntCounterVec::new(
        Opts::new("buildroot_twin_updates_total", "Total number of twin updates"),
        &["type"]  // desired, reported
    ).unwrap();

    /// Twin 获取总数
    pub static ref TWIN_GETS_TOTAL: IntCounter = IntCounter::new(
        "buildroot_twin_gets_total",
        "Total number of twin retrievals"
    ).unwrap();

    /// 缓存命中数
    pub static ref CACHE_HITS: IntCounter = IntCounter::new(
        "buildroot_cache_hits_total",
        "Total number of cache hits"
    ).unwrap();

    /// 缓存未命中数
    pub static ref CACHE_MISSES: IntCounter = IntCounter::new(
        "buildroot_cache_misses_total",
        "Total number of cache misses"
    ).unwrap();

    // ============ 数据库指标 ============

    /// 数据库连接池大小
    pub static ref DB_POOL_SIZE: IntGauge = IntGauge::new(
        "buildroot_db_pool_size",
        "Database connection pool size"
    ).unwrap();

    /// 数据库活跃连接数
    pub static ref DB_POOL_ACTIVE: IntGauge = IntGauge::new(
        "buildroot_db_pool_active",
        "Number of active database connections"
    ).unwrap();

    /// 数据库查询总数
    pub static ref DB_QUERIES_TOTAL: IntCounter = IntCounter::new(
        "buildroot_db_queries_total",
        "Total number of database queries"
    ).unwrap();

    /// 数据库查询错误数
    pub static ref DB_QUERY_ERRORS: IntCounter = IntCounter::new(
        "buildroot_db_query_errors_total",
        "Total number of database query errors"
    ).unwrap();

    // ============ 设备注册指标 ============

    /// 设备注册总数
    pub static ref DEVICE_REGISTRATIONS_TOTAL: IntCounter = IntCounter::new(
        "buildroot_device_registrations_total",
        "Total number of device registrations"
    ).unwrap();

    /// 设备注册失败数
    pub static ref DEVICE_REGISTRATION_ERRORS: IntCounter = IntCounter::new(
        "buildroot_device_registration_errors_total",
        "Total number of device registration errors"
    ).unwrap();
}

/// 初始化指标（注册到 Registry）
pub fn init_metrics() {
    // 设备指标
    REGISTRY.register(Box::new(DEVICES_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(DEVICES_ONLINE.clone())).unwrap();
    REGISTRY.register(Box::new(DEVICES_SYNCED.clone())).unwrap();

    // API 指标
    REGISTRY.register(Box::new(HTTP_REQUESTS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(HTTP_REQUEST_DURATION.clone())).unwrap();
    REGISTRY.register(Box::new(HTTP_REQUESTS_IN_PROGRESS.clone())).unwrap();

    // MQTT 指标
    REGISTRY.register(Box::new(MQTT_CONNECTED.clone())).unwrap();
    REGISTRY.register(Box::new(MQTT_MESSAGES_PUBLISHED.clone())).unwrap();
    REGISTRY.register(Box::new(MQTT_MESSAGES_RECEIVED.clone())).unwrap();
    REGISTRY.register(Box::new(MQTT_PUBLISH_ERRORS.clone())).unwrap();

    // Twin 指标
    REGISTRY.register(Box::new(TWIN_UPDATES_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(TWIN_GETS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(CACHE_HITS.clone())).unwrap();
    REGISTRY.register(Box::new(CACHE_MISSES.clone())).unwrap();

    // 数据库指标
    REGISTRY.register(Box::new(DB_POOL_SIZE.clone())).unwrap();
    REGISTRY.register(Box::new(DB_POOL_ACTIVE.clone())).unwrap();
    REGISTRY.register(Box::new(DB_QUERIES_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(DB_QUERY_ERRORS.clone())).unwrap();

    // 注册指标
    REGISTRY.register(Box::new(DEVICE_REGISTRATIONS_TOTAL.clone())).unwrap();
    REGISTRY.register(Box::new(DEVICE_REGISTRATION_ERRORS.clone())).unwrap();

    tracing::info!("Prometheus metrics initialized");
}

/// 生成 Prometheus 格式的指标输出
pub fn gather() -> String {
    use prometheus::Encoder;
    let encoder = prometheus::TextEncoder::new();
    let metric_families = REGISTRY.gather();
    let mut buffer = Vec::new();
    encoder.encode(&metric_families, &mut buffer).unwrap();
    String::from_utf8(buffer).unwrap()
}