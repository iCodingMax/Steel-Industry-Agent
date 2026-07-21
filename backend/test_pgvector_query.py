"""
测试PGVectorStore的查询行为
"""
import asyncio
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import Document
from app.services.vector_service import VectorIndexService

# 先构建索引
async def build_and_query():
    from app.core.database import SystemAsyncSession
    from app.models.knowledge import KnowledgeBase
    from sqlalchemy import select
    
    async with SystemAsyncSession() as db:
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == 2)
        result = await db.execute(stmt)
        kb = result.scalar_one_or_none()
        
        if not kb:
            print("未找到知识库")
            return
        
        print(f"知识库: {kb.name} (ID={kb.id})")
        
        # 构建索引
        await VectorIndexService.build_index(db, kb)
        print("索引构建完成")
        
        # 获取向量存储
        vs = VectorIndexService._vector_stores.get(kb.id)
        if vs:
            print(f"\n向量存储: {vs.table_name}")
            
            # 测试查询
            from llama_index.core import VectorStoreIndex, QueryBundle
            embed_model = VectorIndexService._get_embed_model()
            
            index = VectorStoreIndex.from_vector_store(vs, embed_model=embed_model)
            retriever = index.as_retriever(similarity_top_k=5)
            
            query_bundle = QueryBundle("解释下什么是高炉炼铁的还原过程？")
            nodes = retriever.retrieve(query_bundle)
            
            print(f"\n查询结果数量: {len(nodes)}")
            for i, node in enumerate(nodes):
                print(f"\n结果{i+1}:")
                print(f"  score: {node.score}")
                print(f"  metadata: {node.metadata}")
                print(f"  text预览: {node.text[:50]}...")
            
            # 检查是否重复
            if len(nodes) > 1:
                first_id = nodes[0].metadata.get("segment_id")
                all_same = all(n.metadata.get("segment_id") == first_id for n in nodes)
                print(f"\n所有结果segment_id相同: {all_same}")

asyncio.run(build_and_query())