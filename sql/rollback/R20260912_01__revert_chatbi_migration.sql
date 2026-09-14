-- =====================================================================
-- 回滚脚本：撤销 V20260912_01（classic→chatbi 存量定向迁移）
-- 执行前提：确认无业务依赖 chatbi 类型行为（意图白名单{data,chat}）
-- =====================================================================

-- 步骤1：定向回滚迁移行（chatbi → classic）
-- 仅回滚本脚本迁移产生的行（绑定特征与规则1一致），
-- 迁移后新增绑定导致特征变化的 chatbi 应用不会被误回滚
-- （CASE WHEN 保证求值顺序，非 NULL 判型在前）
UPDATE applications
SET agent_mode = 'classic',
    updated_at = NOW()
WHERE agent_mode = 'chatbi'
  AND CASE WHEN jsonb_typeof(datasource_ids) = 'array'
           THEN jsonb_array_length(datasource_ids) ELSE 0 END > 0
  AND CASE
        WHEN knowledge_base_ids IS NULL THEN 0
        WHEN jsonb_typeof(knowledge_base_ids) = 'array'
            THEN jsonb_array_length(knowledge_base_ids)
        ELSE 0
      END = 0
  AND CASE
        WHEN tool_config_ids IS NULL THEN 0
        WHEN jsonb_typeof(tool_config_ids) = 'array'
            THEN jsonb_array_length(tool_config_ids)
        ELSE 0
      END = 0;

-- 步骤2：恢复 agent_mode 值域约束（回到 classic/agent 二值，
-- 若仍存在 chatbi 行则约束添加失败——此时需先人工处置这些行）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_applications_agent_mode'
    ) THEN
        ALTER TABLE applications DROP CONSTRAINT ck_applications_agent_mode;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM applications WHERE agent_mode = 'chatbi'
    ) THEN
        ALTER TABLE applications
            ADD CONSTRAINT ck_applications_agent_mode
            CHECK (agent_mode IN ('classic', 'agent'));
    ELSE
        RAISE EXCEPTION '仍存在 agent_mode=chatbi 的应用，请先人工处置后再恢复二值约束';
    END IF;
END $$;

COMMENT ON COLUMN applications.agent_mode IS '执行模式: classic(意图分类路由分发)/agent(智能体ReAct循环)';
