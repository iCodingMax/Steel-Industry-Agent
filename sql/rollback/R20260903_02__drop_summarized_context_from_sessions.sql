-- =====================================================================
-- 回滚脚本：撤销 V20260903_02（sessions 会话记忆摘要列）
-- 执行前提：summarized_context 中无未持久化到 messages 的重要摘要
-- =====================================================================

-- 删除索引
DROP INDEX IF EXISTS idx_sessions_status;

-- 删除列
ALTER TABLE sessions DROP COLUMN IF EXISTS summarized_context;

-- 恢复原 status 注释（去掉挂起态描述）
COMMENT ON COLUMN sessions.status IS '状态: active/archived';

-- 恢复 hybrid 时期 intent_type 注释（如需）
COMMENT ON COLUMN sessions.intent_type IS '会话意图类型: knowledge/data/hybrid';
