"""
检查向量索引数据是否重复
"""
import psycopg
import json

# 连接PostgreSQL系统数据库
conn = psycopg.connect(
    host='localhost',
    port=5432,
    dbname='steel_agent',
    user='postgres',
    password='postgres'
)

cur = conn.cursor()

print("=" * 80)
print("检查document_segments中的重复内容")
print("=" * 80)

cur.execute("""
    SELECT content, COUNT(*) as cnt, knowledge_base_id 
    FROM document_segments 
    GROUP BY content, knowledge_base_id 
    HAVING COUNT(*) > 1 
    ORDER BY cnt DESC
    LIMIT 5
""")
segment_duplicates = cur.fetchall()

if segment_duplicates:
    print(f"发现{len(segment_duplicates)}组重复片段:")
    for content, cnt, kb_id in segment_duplicates:
        print(f"  知识库ID={kb_id}, 重复次数={cnt}, 内容预览: {content[:100]}...")
else:
    print("无重复片段")

# 查看各知识库的片段数量
print("\n" + "=" * 80)
print("各知识库的片段数量")
print("=" * 80)

cur.execute("""
    SELECT kb.id as kb_id, kb.name as kb_name, COUNT(ds.id) as segment_count
    FROM knowledge_bases kb
    LEFT JOIN document_segments ds ON kb.id = ds.knowledge_base_id
    GROUP BY kb.id, kb.name
    ORDER BY kb.id
""")
kb_stats = cur.fetchall()

for kb_id, kb_name, segment_count in kb_stats:
    print(f"  知识库: {kb_name} (ID={kb_id}), 片段数: {segment_count}")
    
    # 查看前3条片段的内容
    cur.execute("""
        SELECT id, content, segment_index 
        FROM document_segments 
        WHERE knowledge_base_id = %s 
        LIMIT 3
    """, (kb_id,))
    segments = cur.fetchall()
    
    for seg_id, content, seg_idx in segments:
        print(f"    片段{seg_idx}: id={seg_id}, 内容长度={len(content)}, 预览: {content[:50]}...")

# 检查所有文档
print("\n" + "=" * 80)
print("所有文档列表")
print("=" * 80)

cur.execute("""
    SELECT d.id, d.file_name, d.knowledge_base_id, d.status
    FROM documents d
    ORDER BY d.id
""")
documents = cur.fetchall()

for doc_id, file_name, kb_id, status in documents:
    print(f"  文档: {file_name} (ID={doc_id}), 知识库ID={kb_id}, 状态={status}")

conn.close()
print("\n检查完成！")