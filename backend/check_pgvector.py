"""
检查PGVectorStore的表名和行为
"""
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import Document

vs = PGVectorStore.from_params(
    database='steel_agent',
    host='localhost',
    password='postgres',
    port=5432,
    user='postgres',
    table_name='kb_2_test',
    embed_dim=1024
)

print(f"table_name: {vs.table_name}")
print(f"Available methods: {[x for x in dir(vs) if not x.startswith('_')]}")

# 查看存储的文档
docs = vs.get_all()
print(f"\n存储的文档数量: {len(docs)}")

# 清理测试表
vs.delete()
print("测试表已删除")