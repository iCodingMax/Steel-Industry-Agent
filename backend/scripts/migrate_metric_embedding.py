"""
方案8 存量迁移脚本：metrics 表加 embedding 列 + 存量指标召回键回填向量化

执行方式（backend 目录下）：
    python -m scripts.migrate_metric_embedding

幂等性：
    - 加列：IF NOT EXISTS，重复执行安全
    - 回填：仅处理 embedding IS NULL 的存量指标，重复执行安全
"""
import asyncio
import json
import sys
from pathlib import Path

# 保证 backend 目录可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import system_engine, SystemAsyncSession


async def add_embedding_column() -> None:
    """metrics 表加 embedding 向量列（幂等）"""
    ddl_list = [
        # pgvector 扩展（已存在则跳过）
        "CREATE EXTENSION IF NOT EXISTS vector",
        # 向量列（1024 维 bge-m3，与 sql_examples 一致）
        "ALTER TABLE metrics ADD COLUMN IF NOT EXISTS embedding vector(1024)",
    ]
    async with system_engine.begin() as conn:
        for ddl in ddl_list:
            await conn.execute(text(ddl))
    print("[OK] metrics.embedding 列已就绪")


async def backfill_embeddings() -> None:
    """存量指标召回键（名称+描述+标签）回填向量化（仅处理 NULL 行，幂等）"""
    from app.models.metric import Metric
    from app.services.sql_example_service import SqlExampleService

    async with SystemAsyncSession() as db:
        rows = (
            (await db.execute(text(
                "SELECT id, name, COALESCE(description, ''), COALESCE(tags, '') "
                "FROM metrics WHERE embedding IS NULL"
            ))).all()
        )
        if not rows:
            print("[OK] 无待回填的存量指标")
            return

        # 逐条向量化（复用 SqlExampleService 的 bge-m3 旁路逻辑）
        for mid, name, desc, tags in rows:
            try:
                tag_list = json.loads(tags) if tags else []
            except Exception:
                tag_list = []
            segments = [name or "", desc or "", " ".join(tag_list)]
            recall_key = " ".join(s for s in segments if s and s.strip())
            if not recall_key.strip():
                print(f"[SKIP] 指标 id={mid} 召回键为空，跳过")
                continue
            vec = await SqlExampleService._embed_question(recall_key)
            if vec is None:
                print(f"[WARN] 指标 id={mid} 向量化失败，跳过（可重跑本脚本重试）")
                continue
            # pgvector 文本格式写入
            vec_str = "[" + ",".join(str(v) for v in vec) + "]"
            await db.execute(
                text("UPDATE metrics SET embedding = :vec WHERE id = :id"),
                {"vec": vec_str, "id": mid},
            )
            print(f"[OK] 指标 id={mid} ({name}) 向量化完成")

        await db.commit()
        print("[DONE] 存量指标回填完成")


async def main() -> None:
    await add_embedding_column()
    await backfill_embeddings()


if __name__ == "__main__":
    asyncio.run(main())
