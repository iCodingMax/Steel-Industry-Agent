-- =====================================================================
-- P3-6c 存量定向迁移：classic 问数型应用定向刷新为 chatbi（方案 2.8.8）
-- 目标库：steel_agent（业务库，PostgreSQL）
-- 说明：
--   1. 存量 classic 应用不批量迁移、不强制改造——仅对"可明确判定
--      语义归属"的应用做一次性定向刷新，其余保持 ChatBot 语义零影响
--   2. 迁移规则（按序判定，命中即停）：
--      规则1（本脚本执行）：已绑定数据源 且 未绑定知识库 且 未绑定
--        tool 配置 → agent_mode='chatbi'（数据源是唯一资源绑定，
--        产品语义即专业问数应用）
--      规则2：已绑定数据源 且 已绑定知识库（或 tool 配置）→ 保持
--        classic（混合绑定语义不明，不自动判定；需问数能力可走
--        2.8.2 受控升级或另存新应用）
--      规则3：未绑定数据源 → 保持 classic（无问数能力，自然归位）
--   3. 先放宽 ck_applications_agent_mode 值域约束以容纳 chatbi
--   4. 幂等设计：WHERE 条件保证重复执行零副作用（已迁移行不再命中）
--   5. 配套回滚脚本：rollback/R20260912_01__revert_chatbi_migration.sql
-- =====================================================================

-- 步骤1：放宽 agent_mode 值域约束（classic/agent → classic/chatbi/agent）
-- 若约束不存在则补建（兼容跳过 V20260903_01 直接执行本脚本的场景）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_applications_agent_mode'
    ) THEN
        ALTER TABLE applications DROP CONSTRAINT ck_applications_agent_mode;
    END IF;

    ALTER TABLE applications
        ADD CONSTRAINT ck_applications_agent_mode
        CHECK (agent_mode IN ('classic', 'chatbi', 'agent'));
END $$;

COMMENT ON COLUMN applications.agent_mode IS '执行模式: classic(对话助手，意图分类路由分发)/chatbi(数据助手，意图白名单{data,chat})/agent(智能体ReAct循环)';

-- 步骤2：存量 NULL 兜底（防御性回填，幂等）
UPDATE applications SET agent_mode = 'classic'
WHERE agent_mode IS NULL;

-- 步骤3：定向迁移（规则1：仅绑数据源的 classic → chatbi）
-- 绑定特征：datasource_ids 非空数组；knowledge_base_ids/tool_config_ids
-- 为 NULL/非数组/空数组均视为未绑定（CASE WHEN 保证求值顺序，
-- 非 NULL 判型在前，避免 jsonb_array_length 对非数组抛错）
UPDATE applications
SET agent_mode = 'chatbi',
    updated_at = NOW()
WHERE (agent_mode = 'classic' OR agent_mode IS NULL)
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

-- 步骤4：迁移结果审计查询（手工执行核对，非脚本必须步骤）
-- 预期：chatbi 应用均满足规则1绑定特征；classic 应用行为零变化
-- SELECT id, name, agent_mode, knowledge_base_ids, datasource_ids, tool_config_ids
-- FROM applications ORDER BY agent_mode, id;
