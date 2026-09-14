-- =====================================================================
-- 智能体升级一期：sessions 表新增会话记忆摘要列
-- 目标库：steel_agent（业务库）
-- 说明：
--   1. summarized_context 存储长对话滚动摘要（history超阈值时LLM压缩）
--   2. status 值域扩展 awaiting_input（interrupt挂起态）/expired（超时过期）
--   3. 定稿决策：原 pending_task 字段取消，interrupt 挂起任务由
--      LangGraph Checkpointer 原生承载（thread_id=session_id）
--   4. 配套回滚脚本：rollback/R20260903_02__drop_summarized_context_from_sessions.sql
-- =====================================================================

-- 添加会话滚动摘要列
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summarized_context TEXT;

-- 添加列注释
COMMENT ON COLUMN sessions.summarized_context IS '会话记忆滚动摘要(LLM压缩后的历史上下文,history超12条时生成)';

-- status 值域扩展说明（VARCHAR列无需DDL，仅更新注释）
COMMENT ON COLUMN sessions.status IS '状态: active(活跃)/archived(归档)/awaiting_input(等待用户输入)/expired(挂起超时过期)';

-- 防御性修正：历史intent_type注释中的hybrid值域描述清理（M4 hybrid下线配套）
COMMENT ON COLUMN sessions.intent_type IS '会话意图类型: knowledge/data/mcp/skill/chat';

-- 挂起会话超时清理索引（支持7天TTL cron按status扫描过期）
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions (status);
