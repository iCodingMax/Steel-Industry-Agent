-- 为 applications 表添加 tool_config_ids 列
ALTER TABLE applications ADD COLUMN IF NOT EXISTS tool_config_ids JSONB DEFAULT '[]'::jsonb;

-- 添加列注释
COMMENT ON COLUMN applications.tool_config_ids IS '关联工具配置ID列表(MCP/Skills)';

-- 更新现有数据，确保默认值为空数组
UPDATE applications SET tool_config_ids = '[]'::jsonb WHERE tool_config_ids IS NULL;
