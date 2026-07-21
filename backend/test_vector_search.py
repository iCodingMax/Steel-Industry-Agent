"""
测试向量检索行为
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.vector_service import VectorIndexService
from app.core.database import SystemAsyncSession
from app.models.knowledge import KnowledgeBase
from app.schemas.knowledge import KnowledgeQuery


async def test_search():
    """测试向量检索"""
    print("=" * 80)
    print("测试向量检索")
    print("=" * 80)
    
    async with SystemAsyncSession() as db:
        # 获取知识库
        from sqlalchemy import select
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == 2)  # 高炉炼铁知识
        result = await db.execute(stmt)
        kb = result.scalar_one_or_none()
        
        if not kb:
            print("未找到知识库")
            return
        
        print(f"知识库: {kb.name} (ID={kb.id})")
        
        # 创建查询
        query = KnowledgeQuery(
            knowledgeBaseId=kb.id,
            question="解释下什么是高炉炼铁的还原过程？",
            topK=5
        )
        
        # 执行检索
        try:
            results = await VectorIndexService.search(db, query, kb)
            
            print(f"\n检索结果数量: {len(results)}")
            
            for i, r in enumerate(results):
                print(f"\n结果{i+1}:")
                print(f"  segmentId: {r.segmentId}")
                print(f"  documentId: {r.documentId}")
                print(f"  documentName: {r.documentName}")
                print(f"  score: {r.score}")
                print(f"  content预览: {r.content[:100]}...")
            
            # 检查是否有重复
            if len(results) > 1:
                first_content = results[0].content
                all_same = all(r.content == first_content for r in results)
                all_same_score = all(r.score == results[0].score for r in results)
                
                print(f"\n所有内容相同: {all_same}")
                print(f"所有分数相同: {all_same_score}")
                
        except Exception as e:
            print(f"检索失败: {e}")


async def test_index_build():
    """测试索引构建"""
    print("\n" + "=" * 80)
    print("测试索引构建")
    print("=" * 80)
    
    async with SystemAsyncSession() as db:
        from sqlalchemy import select
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == 2)
        result = await db.execute(stmt)
        kb = result.scalar_one_or_none()
        
        if not kb:
            print("未找到知识库")
            return
        
        print(f"构建知识库: {kb.name} (ID={kb.id})")
        
        try:
            count = await VectorIndexService.build_index(db, kb)
            print(f"索引构建完成，索引文档数量: {count}")
        except Exception as e:
            print(f"索引构建失败: {e}")


async def main():
    """主测试函数"""
    # 先测试索引构建
    await test_index_build()
    
    # 再测试检索
    await test_search()


if __name__ == "__main__":
    asyncio.run(main())