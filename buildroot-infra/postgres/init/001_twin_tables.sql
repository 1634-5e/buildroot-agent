-- Buildroot Agent Device Twin 数据库初始化
-- 版本: 1.0.0
-- 创建时间: 2026-03-11

-- ==================== 设备孪生主表 ====================
CREATE TABLE IF NOT EXISTS device_twins (
    device_id VARCHAR(64) PRIMARY KEY,
    
    -- 期望状态（云端定义）
    desired JSONB NOT NULL DEFAULT '{}',
    desired_version BIGINT NOT NULL DEFAULT 0,
    desired_at TIMESTAMP WITH TIME ZONE,
    desired_by VARCHAR(128),
    
    -- 已报告状态（设备上报）
    reported JSONB NOT NULL DEFAULT '{}',
    reported_version BIGINT NOT NULL DEFAULT 0,
    reported_at TIMESTAMP WITH TIME ZONE,
    
    -- 标签（云端管理）
    tags JSONB NOT NULL DEFAULT '{}',
    
    -- 元数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 约束
    CONSTRAINT valid_device_id CHECK (device_id ~ '^[A-Za-z0-9_-]+$')
);

COMMENT ON TABLE device_twins IS '设备孪生表 - 存储设备的期望状态和已报告状态';
COMMENT ON COLUMN device_twins.desired IS '期望状态：云端希望设备达到的状态';
COMMENT ON COLUMN device_twins.reported IS '已报告状态：设备实际上报的状态';
COMMENT ON COLUMN device_twins.tags IS '标签：用于分类和筛选设备';

-- ==================== 状态变更历史表 ====================
CREATE TABLE IF NOT EXISTS twin_change_logs (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES device_twins(device_id) ON DELETE CASCADE,
    
    -- 变更详情
    change_type VARCHAR(16) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    
    -- 变更来源
    changed_by VARCHAR(128),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 约束
    CONSTRAINT valid_change_type CHECK (change_type IN ('desired', 'reported'))
);

COMMENT ON TABLE twin_change_logs IS '状态变更历史表 - 记录所有状态变更用于审计';
COMMENT ON COLUMN twin_change_logs.change_type IS '变更类型：desired 或 reported';

-- ==================== 索引 ====================

-- 设备查询优化
CREATE INDEX IF NOT EXISTS idx_twins_desired_at ON device_twins(desired_at DESC);
CREATE INDEX IF NOT EXISTS idx_twins_reported_at ON device_twins(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_twins_tags ON device_twins USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_twins_created_at ON device_twins(created_at DESC);

-- 变更历史查询优化
CREATE INDEX IF NOT EXISTS idx_change_logs_device ON twin_change_logs(device_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_logs_type ON twin_change_logs(change_type);
CREATE INDEX IF NOT EXISTS idx_change_logs_time ON twin_change_logs(changed_at DESC);

-- ==================== 触发器 ====================

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_twin_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS twin_updated ON device_twins;
CREATE TRIGGER twin_updated
    BEFORE UPDATE ON device_twins
    FOR EACH ROW
    EXECUTE FUNCTION update_twin_timestamp();

-- ==================== 初始测试数据 ====================

-- 插入测试设备
INSERT INTO device_twins (device_id, desired, reported, tags)
VALUES 
    ('HTCU-DEV-001', 
     '{"firmware": {"version": "2.0.5"}, "config": {"sampleRate": 1000}}',
     '{"firmware": {"version": "2.0.4"}, "config": {"sampleRate": 500}}',
     '{"location": "lab", "env": "development"}'
    ),
    ('HTCU-DEV-002',
     '{"config": {"logLevel": "info"}}',
     '{"firmware": {"version": "2.0.5"}, "config": {"logLevel": "debug"}}',
     '{"location": "lab", "env": "development"}'
    )
ON CONFLICT (device_id) DO NOTHING;

-- ==================== 视图：设备状态概览 ====================
CREATE OR REPLACE VIEW v_device_overview AS
SELECT 
    device_id,
    desired_version,
    reported_version,
    desired_at,
    reported_at,
    tags,
    created_at,
    updated_at,
    -- 计算 delta（简化版，只比较顶层 key）
    (
        SELECT jsonb_object_agg(key, value)
        FROM jsonb_each(desired) AS d(key, value)
        WHERE NOT reported ? key OR reported->key != value
    ) AS delta,
    -- 判断是否同步
    CASE 
        WHEN desired = reported THEN true 
        ELSE false 
    END AS is_synced
FROM device_twins;

COMMENT ON VIEW v_device_overview IS '设备状态概览视图 - 显示同步状态和差异';

-- ==================== 函数：计算完整 delta ====================
CREATE OR REPLACE FUNCTION compute_twin_delta(p_device_id VARCHAR(64))
RETURNS JSONB AS $$
DECLARE
    v_desired JSONB;
    v_reported JSONB;
    v_delta JSONB;
BEGIN
    SELECT desired, reported INTO v_desired, v_reported
    FROM device_twins WHERE device_id = p_device_id;
    
    IF v_desired IS NULL THEN
        RETURN '{}'::JSONB;
    END IF;
    
    -- 递归计算差异
    v_delta := compute_jsonb_delta(v_desired, COALESCE(v_reported, '{}'::JSONB));
    
    RETURN v_delta;
END;
$$ LANGUAGE plpgsql;

-- 递归计算 JSONB 差异的辅助函数
CREATE OR REPLACE FUNCTION compute_jsonb_delta(p_desired JSONB, p_reported JSONB)
RETURNS JSONB AS $$
DECLARE
    v_delta JSONB := '{}'::JSONB;
    v_key TEXT;
    v_desired_val JSONB;
    v_reported_val JSONB;
BEGIN
    FOR v_key, v_desired_val IN SELECT * FROM jsonb_each(p_desired) LOOP
        v_reported_val := p_reported->v_key;
        
        -- reported 中不存在该 key
        IF v_reported_val IS NULL THEN
            v_delta := v_delta || jsonb_build_object(v_key, v_desired_val);
        -- 两者都是对象，递归比较
        ELSIF jsonb_typeof(v_desired_val) = 'object' AND jsonb_typeof(v_reported_val) = 'object' THEN
            DECLARE
                v_nested_delta JSONB;
            BEGIN
                v_nested_delta := compute_jsonb_delta(v_desired_val, v_reported_val);
                IF jsonb_object_keys(v_nested_delta) IS NOT NULL THEN
                    v_delta := v_delta || jsonb_build_object(v_key, v_nested_delta);
                END IF;
            EXCEPTION WHEN OTHERS THEN
                v_delta := v_delta || jsonb_build_object(v_key, v_desired_val);
            END;
        -- 值不同
        ELSIF v_desired_val != v_reported_val THEN
            v_delta := v_delta || jsonb_build_object(v_key, v_desired_val);
        END IF;
    END LOOP;
    
    RETURN v_delta;
END;
$$ LANGUAGE plpgsql;

-- ==================== 权限 ====================

-- 创建只读用户（可选）
-- CREATE USER buildroot_readonly WITH PASSWORD 'readonly123';
-- GRANT CONNECT ON DATABASE buildroot_agent TO buildroot_readonly;
-- GRANT USAGE ON SCHEMA public TO buildroot_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO buildroot_readonly;

-- ==================== 完成 ====================
-- 初始化完成提示
DO $$
BEGIN
    RAISE NOTICE 'Device Twin 数据库初始化完成';
    RAISE NOTICE '测试设备: HTCU-DEV-001, HTCU-DEV-002';
END $$;