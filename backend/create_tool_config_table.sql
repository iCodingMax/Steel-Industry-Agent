-- 工具配置表
CREATE TABLE IF NOT EXISTS tool_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    tool_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    mcp_config JSONB,
    skill_file_path VARCHAR(500),
    skill_file_name VARCHAR(255),
    icon VARCHAR(255),
    timeout INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
);

-- 添加表注释
COMMENT ON TABLE tool_configs IS '工具配置表（MCP Server 和 Skills）';

-- 添加列注释
COMMENT ON COLUMN tool_configs.id IS '工具ID';
COMMENT ON COLUMN tool_configs.name IS '工具名称';
COMMENT ON COLUMN tool_configs.description IS '工具描述';
COMMENT ON COLUMN tool_configs.tool_type IS '工具类型: mcp/skill';
COMMENT ON COLUMN tool_configs.status IS '状态: active/inactive';
COMMENT ON COLUMN tool_configs.mcp_config IS 'MCP Server配置(JSON)';
COMMENT ON COLUMN tool_configs.skill_file_path IS 'Skill文件存储路径';
COMMENT ON COLUMN tool_configs.skill_file_name IS 'Skill原始文件名';
COMMENT ON COLUMN tool_configs.icon IS '图标';
COMMENT ON COLUMN tool_configs.timeout IS '执行超时时间(秒)';
COMMENT ON COLUMN tool_configs.created_at IS '创建时间';
COMMENT ON COLUMN tool_configs.updated_at IS '更新时间';
COMMENT ON COLUMN tool_configs.created_by IS '创建人ID';
