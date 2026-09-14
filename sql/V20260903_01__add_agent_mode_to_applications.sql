-- =====================================================================
-- 智能体升级一期：applications 表新增智能体模式配置
-- 目标库：steel_agent（业务库）
-- 说明：
--   1. agent_mode 为应用级灰度开关，默认 classic 保证存量应用零感知
--   2. agent_max_iterations 限制 MasterAgent ReAct 循环最大迭代次数
--   3. 配套回滚脚本：rollback/R20260903_01__drop_agent_mode_from_applications.sql
-- =====================================================================

-- 添加执行模式列
ALTER TABLE applications ADD COLUMN IF NOT EXISTS agent_mode VARCHAR(10) DEFAULT 'classic';

-- 添加最大迭代次数列
ALTER TABLE applications ADD COLUMN IF NOT EXISTS agent_max_iterations INTEGER DEFAULT 8;

-- 添加列注释
COMMENT ON COLUMN applications.agent_mode IS '执行模式: classic(意图分类路由分发)/agent(智能体ReAct循环)';
COMMENT ON COLUMN applications.agent_max_iterations IS 'Agent模式最大推理迭代次数(防死循环,默认8)';

-- 值域约束（仅新增，重复执行不报错）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_applications_agent_mode'
    ) THEN
        ALTER TABLE applications
            ADD CONSTRAINT ck_applications_agent_mode
            CHECK (agent_mode IN ('classic', 'agent'));
    END IF;
END $$;

-- 迭代次数下限约束（防误配为0导致Agent无法执行）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_applications_agent_max_iterations'
    ) THEN
        ALTER TABLE applications
            ADD CONSTRAINT ck_applications_agent_max_iterations
            CHECK (agent_max_iterations >= 1 AND agent_max_iterations <= 32);
    END IF;
END $$;

-- 存量数据回填默认值（保证 NOT NULL 语义上成立）
UPDATE applications SET agent_mode = 'classic' WHERE agent_mode IS NULL;
UPDATE applications SET agent_max_iterations = 8 WHERE agent_max_iterations IS NULL;
