-- =====================================================================
-- 智能体升级一期：创建长期记忆表 agent_memories（三层记忆之长期记忆层）
-- 目标库：steel_agent（业务库，已启用 pgvector 扩展，见 scripts/init_pg.sh）
-- 说明：
--   1. 存储：用户偏好/设备档案/诊断结论，bge-m3 向量化（维度1024）
--   2. 写入：MasterAgent finalize 节点提取带数据支撑的结论沉淀
--   3. 检索：planner 节点前按 application+user 向量检索注入上下文
--   4. 治理：人工清理接口 + expires_at 时效控制（防记忆污染 R7）
--   5. 配套回滚脚本：rollback/R20260903_03__drop_agent_memories.sql
-- =====================================================================

CREATE TABLE IF NOT EXISTS agent_memories (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL,
    user_id INTEGER,
    memory_type VARCHAR(30) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1024),
    session_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- 添加表注释
COMMENT ON TABLE agent_memories IS '智能体长期记忆表(用户偏好/设备档案/诊断结论,pgvector向量检索)';

-- 添加列注释
COMMENT ON COLUMN agent_memories.id IS '记忆ID';
COMMENT ON COLUMN agent_memories.application_id IS '所属应用ID(应用级记忆隔离)';
COMMENT ON COLUMN agent_memories.user_id IS '关联用户ID(为空表示应用级公共记忆)';
COMMENT ON COLUMN agent_memories.memory_type IS '记忆类型: preference(用户偏好)/fact(设备档案)/diagnosis_conclusion(诊断结论)';
COMMENT ON COLUMN agent_memories.content IS '记忆文本内容';
COMMENT ON COLUMN agent_memories.embedding IS '记忆内容向量(bge-m3,1024维)';
COMMENT ON COLUMN agent_memories.session_id IS '来源会话ID(溯源用,指向sessions.id)';
COMMENT ON COLUMN agent_memories.created_at IS '创建时间';
COMMENT ON COLUMN agent_memories.expires_at IS '过期时间(为空表示永久有效,如本周炉况类时效记忆设置过期)';

-- 外键约束（应用删除时级联清理记忆）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_agent_memories_application'
    ) THEN
        ALTER TABLE agent_memories
            ADD CONSTRAINT fk_agent_memories_application
            FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 应用+用户维度检索索引（planner前检索入口）
CREATE INDEX IF NOT EXISTS idx_agent_memories_app_user
    ON agent_memories (application_id, user_id);

-- memory_type 过滤索引（按类型清理/检索）
CREATE INDEX IF NOT EXISTS idx_agent_memories_type
    ON agent_memories (memory_type);

-- 过期时间索引（TTL cron 扫描）
CREATE INDEX IF NOT EXISTS idx_agent_memories_expires
    ON agent_memories (expires_at);

-- HNSW 向量索引（pgvector 0.5+，pg16镜像原生支持）
-- 距离度量：cosine（与 bge-m3 嵌入的相似度语义一致）
CREATE INDEX IF NOT EXISTS idx_agent_memories_embedding_hnsw
    ON agent_memories USING hnsw (embedding vector_cosine_ops);
