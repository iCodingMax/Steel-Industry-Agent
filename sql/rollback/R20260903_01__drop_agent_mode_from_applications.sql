-- =====================================================================
-- 回滚脚本：撤销 V20260903_01（applications 智能体模式列）
-- 执行前提：确认无 agent_mode='agent' 的应用，或已将其切回 classic
-- =====================================================================

-- 删除值域约束
ALTER TABLE applications DROP CONSTRAINT IF EXISTS ck_applications_agent_max_iterations;
ALTER TABLE applications DROP CONSTRAINT IF EXISTS ck_applications_agent_mode;

-- 删除列（agent_mode 回填 'classic' 后删除不丢失业务语义）
ALTER TABLE applications DROP COLUMN IF EXISTS agent_mode;
ALTER TABLE applications DROP COLUMN IF EXISTS agent_max_iterations;
