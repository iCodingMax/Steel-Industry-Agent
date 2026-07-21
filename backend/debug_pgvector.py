"""
调试PGVectorStore的存储和查询行为
"""
import asyncio
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import Document, VectorStoreIndex, StorageContext, QueryBundle

async def debug_pgvector():
    # 创建PGVectorStore
    vs = PGVectorStore.from_params(
        database='steel_agent',
        host='localhost',
        password='postgres',
        port=5432,
        user='postgres',
        table_name='kb_debug_test',
        embed_dim=1024
    )
    
    print(f"table_name: {vs.table_name}")
    print(f"connection_string: {vs.connection_string}")
    
    # 创建测试文档
    docs = [
        Document(text="文档1: 高炉炼铁的还原过程是将铁矿石中的铁氧化物还原为金属铁", 
                 metadata={"segment_id": 1, "document_id": 1}),
        Document(text="文档2: 转炉炼钢是通过氧化反应去除铁水中的杂质", 
                 metadata={"segment_id": 2, "document_id": 1}),
        Document(text="文档3: 轧钢工艺是将钢坯加工成各种形状的钢材", 
                 metadata={"segment_id": 3, "document_id": 2}),
    ]
    
    # 创建存储上下文并添加文档
    storage_context = StorageContext.from_defaults(vector_store=vs)
    
    # 使用已定义的嵌入模型
    from app.services.vector_service import VectorIndexService
    embed_model = VectorIndexService._get_embed_model()
    
    # 构建索引
    index = VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        embed_model=embed_model,
    )
    
    print("\n索引构建完成")
    
    # 测试查询
    retriever = index.as_retriever(similarity_top_k=3)
    query_bundle = QueryBundle("高炉炼铁")
    nodes = retriever.retrieve(query_bundle)
    
    print(f"\n查询结果数量: {len(nodes)}")
    for i, node in enumerate(nodes):
        print(f"\n结果{i+1}:")
        print(f"  score: {node.score}")
        print(f"  metadata: {node.metadata}")
        print(f"  text: {node.text}")
    
    # 检查是否重复
    if len(nodes) > 1:
        first_id = nodes[0].metadata.get("segment_id")
        all_same = all(n.metadata.get("segment_id") == first_id for n in nodes)
        print(f"\n所有结果segment_id相同: {all_same}")
    
    # 删除测试表
    vs.delete()
    print("\n测试表已删除")

asyncio.run(debug_pgvector())