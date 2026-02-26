-- ============================================================================
-- Buildroot Agent Server Database Initialization Script
-- Version: 2.0.0
-- Description: Initialize database schema for buildroot-agent server
-- Requirements: PostgreSQL 13+
-- Note: Simplified version without extensions, enums, partitions, functions, views
-- ============================================================================

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255),
    version VARCHAR(20),
    hostname VARCHAR(100),
    kernel_version VARCHAR(50),
    ip_addr VARCHAR(45),
    mac_addr VARCHAR(17),
    status VARCHAR(16) DEFAULT 'offline',
    is_online BOOLEAN DEFAULT FALSE,
    last_connected_at TIMESTAMP WITH TIME ZONE,
    last_disconnected_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    current_status JSONB,
    last_status_reported_at TIMESTAMP WITH TIME ZONE,
    update_channel VARCHAR(50) DEFAULT 'stable',
    auto_update BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tags JSONB,
    total_uptime_seconds BIGINT DEFAULT 0,
    connection_count INT DEFAULT 0
);

-- Device status history table
CREATE TABLE IF NOT EXISTS device_status_history (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    reported_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    cpu_usage NUMERIC(5,2),
    cpu_cores INT,
    cpu_user NUMERIC(5,2),
    cpu_system NUMERIC(5,2),
    mem_total NUMERIC(10,2),
    mem_used NUMERIC(10,2),
    mem_free NUMERIC(10,2),
    mem_usage_percent NUMERIC(5,2),
    disk_total NUMERIC(12,2),
    disk_used NUMERIC(12,2),
    disk_usage_percent NUMERIC(5,2),
    load_1min NUMERIC(5,2),
    load_5min NUMERIC(5,2),
    load_15min NUMERIC(5,2),
    uptime INT,
    net_rx_bytes BIGINT,
    net_tx_bytes BIGINT,
    hostname VARCHAR(100),
    kernel_version VARCHAR(50),
    ip_addr VARCHAR(45),
    mac_addr VARCHAR(17),
    raw_data JSONB
);

-- Web console sessions table
CREATE TABLE IF NOT EXISTS web_console_sessions (
    id BIGSERIAL PRIMARY KEY,
    console_id VARCHAR(50) UNIQUE NOT NULL,
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    disconnected_at TIMESTAMP WITH TIME ZONE,
    device_id VARCHAR(64),
    remote_addr VARCHAR(45),
    user_agent TEXT,
    pty_sessions_count INT DEFAULT 0,
    commands_sent INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    user_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- PTY sessions table
CREATE TABLE IF NOT EXISTS pty_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id INT NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    console_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    closed_reason VARCHAR(50),
    rows INT DEFAULT 24,
    cols INT DEFAULT 80,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'active',
    created_by VARCHAR(50)
);

-- Command history table
CREATE TABLE IF NOT EXISTS command_history (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    console_id VARCHAR(50),
    request_id VARCHAR(50) UNIQUE,
    command TEXT NOT NULL,
    command_type VARCHAR(50) DEFAULT 'shell',
    status VARCHAR(16) DEFAULT 'pending',
    exit_code INT,
    success BOOLEAN,
    stdout TEXT,
    stderr TEXT,
    output_summary TEXT,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INT,
    script_id VARCHAR(50),
    metadata JSONB,
    error_message TEXT
);

-- Script history table
CREATE TABLE IF NOT EXISTS script_history (
    id BIGSERIAL PRIMARY KEY,
    script_id VARCHAR(50) NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    console_id VARCHAR(50),
    request_id VARCHAR(50) UNIQUE,
    script_name VARCHAR(100),
    script_content TEXT,
    script_type VARCHAR(50) DEFAULT 'bash',
    status VARCHAR(16) DEFAULT 'pending',
    exit_code INT,
    success BOOLEAN,
    output TEXT,
    output_summary TEXT,
    output_size INT,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INT,
    error_message TEXT,
    metadata JSONB
);

-- File transfers table
CREATE TABLE IF NOT EXISTS file_transfers (
    id BIGSERIAL PRIMARY KEY,
    transfer_id VARCHAR(50) UNIQUE NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    console_id VARCHAR(50),
    filename VARCHAR(100) NOT NULL,
    filepath VARCHAR(200),
    file_size BIGINT,
    direction VARCHAR(50) NOT NULL,
    action_type VARCHAR(50),
    status VARCHAR(16) DEFAULT 'pending',
    checksum VARCHAR(32),
    checksum_verified BOOLEAN DEFAULT FALSE,
    chunk_size INT,
    total_chunks INT,
    transferred_chunks INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INT,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    request_id VARCHAR(50),
    metadata JSONB
);

-- Update history table
CREATE TABLE IF NOT EXISTS update_history (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    old_version VARCHAR(50),
    new_version VARCHAR(50),
    update_channel VARCHAR(50),
    package_name VARCHAR(100),
    package_size BIGINT,
    package_checksum VARCHAR(32),
    package_url TEXT,
    status VARCHAR(16) DEFAULT 'pending',
    mandatory BOOLEAN DEFAULT FALSE,
    approval_required BOOLEAN DEFAULT FALSE,
    download_approved_at TIMESTAMP WITH TIME ZONE,
    install_approved_at TIMESTAMP WITH TIME ZONE,
    approval_reason TEXT,
    check_requested_at TIMESTAMP WITH TIME ZONE,
    download_started_at TIMESTAMP WITH TIME ZONE,
    download_completed_at TIMESTAMP WITH TIME ZONE,
    install_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    backup_path TEXT,
    backup_version VARCHAR(50),
    rollback_requested_at TIMESTAMP WITH TIME ZONE,
    rollback_completed_at TIMESTAMP WITH TIME ZONE,
    rollback_reason TEXT,
    error_message TEXT,
    error_stage VARCHAR(50),
    request_id VARCHAR(50) UNIQUE,
    release_notes TEXT,
    changes JSONB,
    metadata JSONB
);

-- Update approvals table
CREATE TABLE IF NOT EXISTS update_approvals (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    update_history_id BIGINT REFERENCES update_history(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    version VARCHAR(50),
    file_size BIGINT,
    approval_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    console_id VARCHAR(50),
    reason VARCHAR(64),
    approved_by VARCHAR(50),
    approved_by_ip VARCHAR(45),
    request_id VARCHAR(50),
    metadata JSONB
);

-- ping_history table
CREATE TABLE IF NOT EXISTS ping_history (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    reported_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    target_ip VARCHAR(45) NOT NULL,
    status INT DEFAULT 0,
    avg_time NUMERIC(8,3),
    min_time NUMERIC(8,3),
    max_time NUMERIC(8,3),
    packet_loss NUMERIC(5,2),
    packets_sent INT DEFAULT 0,
    packets_received INT DEFAULT 0,
    raw_data JSONB
);



-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    event_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actor_type VARCHAR(50),
    actor_id VARCHAR(100),
    device_id VARCHAR(64),
    console_id VARCHAR(50),
    user_id VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    status VARCHAR(16) DEFAULT 'success',
    result_message TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB
);


-- ============================================================================
-- 2. 索引创建
-- ============================================================================

-- Basic indexes
CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_devices_created ON devices(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_devices_is_online ON devices(is_online);

-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_devices_tags_gin ON devices USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_devices_current_status_gin ON devices USING GIN (current_status);
CREATE INDEX IF NOT EXISTS idx_device_status_history_raw_data_gin ON device_status_history USING GIN (raw_data);
CREATE INDEX IF NOT EXISTS idx_command_history_metadata_gin ON command_history USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_script_history_metadata_gin ON script_history USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_file_transfers_metadata_gin ON file_transfers USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_update_history_metadata_gin ON update_history USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_update_history_changes_gin ON update_history USING GIN (changes);
CREATE INDEX IF NOT EXISTS idx_update_approvals_metadata_gin ON update_approvals USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_audit_logs_details_gin ON audit_logs USING GIN (details);
CREATE INDEX IF NOT EXISTS idx_ping_history_raw_data_gin ON ping_history USING GIN (raw_data);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_devices_device_status ON devices(device_id, status);
CREATE INDEX IF NOT EXISTS idx_devices_device_is_online ON devices(device_id, is_online);
CREATE INDEX IF NOT EXISTS idx_device_status_history_device_reported ON device_status_history(device_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_history_device_status_requested ON command_history(device_id, status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_history_device_requested ON command_history(device_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_device_event_time ON audit_logs(device_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type_time ON audit_logs(event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_device_event_type_time ON audit_logs(device_id, event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_pty_sessions_device_status ON pty_sessions(device_id, status);
CREATE INDEX IF NOT EXISTS idx_pty_sessions_device_console_status ON pty_sessions(device_id, console_id, status);
CREATE INDEX IF NOT EXISTS idx_file_transfers_device_status_created ON file_transfers(device_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_update_history_device_status_requested ON update_history(device_id, status, check_requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_update_history_device_channel ON update_history(device_id, update_channel);

-- Partial indexes for ORDER BY optimization
CREATE INDEX IF NOT EXISTS idx_devices_device_seen_at_desc ON devices(device_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_status_history_device_reported_desc ON device_status_history(device_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_history_device_requested_desc ON command_history(device_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_update_history_device_check_requested_desc ON update_history(device_id, check_requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_time_desc ON audit_logs(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_web_console_sessions_device_connected_desc ON web_console_sessions(device_id, connected_at DESC);

-- Covering indexes to reduce table lookups
CREATE INDEX IF NOT EXISTS idx_devices_device_cover ON devices(device_id, status, is_online, last_seen_at) INCLUDE (name, version, created_at);
CREATE INDEX IF NOT EXISTS idx_command_history_device_cover ON command_history(device_id, status, requested_at DESC) INCLUDE (command_type, exit_code, success);
CREATE INDEX IF NOT EXISTS idx_audit_logs_device_cover ON audit_logs(device_id, event_time DESC) INCLUDE (event_type, action, status);

-- Basic indexes for other tables
CREATE INDEX IF NOT EXISTS idx_device_status_history_device_id ON device_status_history(device_id);
CREATE INDEX IF NOT EXISTS idx_device_status_history_reported_at ON device_status_history(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_status_history_device_reported ON device_status_history(device_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_console_sessions_console_id ON web_console_sessions(console_id);
CREATE INDEX IF NOT EXISTS idx_web_console_sessions_device_id ON web_console_sessions(device_id);
CREATE INDEX IF NOT EXISTS idx_web_console_sessions_is_active ON web_console_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_web_console_sessions_connected_at ON web_console_sessions(connected_at DESC);
CREATE INDEX IF NOT EXISTS idx_pty_sessions_device_id ON pty_sessions(device_id);
CREATE INDEX IF NOT EXISTS idx_pty_sessions_console_id ON pty_sessions(console_id);
CREATE INDEX IF NOT EXISTS idx_pty_sessions_created_at ON pty_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pty_sessions_status ON pty_sessions(status);
CREATE INDEX IF NOT EXISTS idx_command_history_device_id ON command_history(device_id);
CREATE INDEX IF NOT EXISTS idx_command_history_console_id ON command_history(console_id);
CREATE INDEX IF NOT EXISTS idx_command_history_request_id ON command_history(request_id);
CREATE INDEX IF NOT EXISTS idx_command_history_status ON command_history(status);
CREATE INDEX IF NOT EXISTS idx_command_history_requested_at ON command_history(requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_history_command_type ON command_history(command_type);
CREATE INDEX IF NOT EXISTS idx_script_history_script_id ON script_history(script_id);
CREATE INDEX IF NOT EXISTS idx_script_history_device_id ON script_history(device_id);
CREATE INDEX IF NOT EXISTS idx_script_history_requested_at ON script_history(requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_script_history_status ON script_history(status);
CREATE INDEX IF NOT EXISTS idx_file_transfers_transfer_id ON file_transfers(transfer_id);
CREATE INDEX IF NOT EXISTS idx_file_transfers_device_id ON file_transfers(device_id);
CREATE INDEX IF NOT EXISTS idx_file_transfers_status ON file_transfers(status);
CREATE INDEX IF NOT EXISTS idx_file_transfers_direction ON file_transfers(direction);
CREATE INDEX IF NOT EXISTS idx_file_transfers_created_at ON file_transfers(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_update_history_device_id ON update_history(device_id);
CREATE INDEX IF NOT EXISTS idx_update_history_status ON update_history(status);
CREATE INDEX IF NOT EXISTS idx_update_history_new_version ON update_history(new_version);
CREATE INDEX IF NOT EXISTS idx_update_history_completed_at ON update_history(completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_update_history_request_id ON update_history(request_id);
CREATE INDEX IF NOT EXISTS idx_update_approvals_device_id ON update_approvals(device_id);
CREATE INDEX IF NOT EXISTS idx_update_approvals_update_history_id ON update_approvals(update_history_id);
CREATE INDEX IF NOT EXISTS idx_update_approvals_action ON update_approvals(action);
CREATE INDEX IF NOT EXISTS idx_update_approvals_approval_time ON update_approvals(approval_time DESC);
-- ping_history indexes
CREATE INDEX IF NOT EXISTS idx_ping_history_device_id ON ping_history(device_id);
CREATE INDEX IF NOT EXISTS idx_ping_history_target_ip ON ping_history(target_ip);
CREATE INDEX IF NOT EXISTS idx_ping_history_reported_at ON ping_history(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_ping_history_device_reported ON ping_history(device_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_ping_history_device_target ON ping_history(device_id, target_ip);
CREATE INDEX IF NOT EXISTS idx_ping_history_status ON ping_history(status);
CREATE INDEX IF NOT EXISTS idx_update_approvals_update_history_id ON update_approvals(update_history_id);
CREATE INDEX IF NOT EXISTS idx_update_approvals_action ON update_approvals(action);
CREATE INDEX IF NOT EXISTS idx_update_approvals_approval_time ON update_approvals(approval_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_device_id ON audit_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_time ON audit_logs(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_type, actor_id);

-- ============================================================================
-- 3. 完成信息
-- ============================================================================

-- Schema initialized successfully!
-- Tables created: 10
-- Indexes created: 50+ (B-tree + GIN)
-- Optimizations applied:
--   - GIN indexes on all JSONB fields
--   - Composite indexes for device_id + status/time patterns
--   - Partial indexes (DESC) for ORDER BY queries
--   - Covering indexes to reduce table lookups
--   - Reduced VARCHAR sizes for frequently queried fields
