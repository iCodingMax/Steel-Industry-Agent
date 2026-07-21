"""
检查向量表中的数据是否重复
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
print("检查向量表 kb_2 的数据")
print("=" * 80)

# 检查向量表结构
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'kb_2'
    ORDER BY ordinal_position
""")
columns = cur.fetchall()
print("向量表结构:")
for col_name, data_type in columns:
    print(f"  {col_name}: {data_type}")

# 统计记录数
cur.execute("SELECT COUNT(*) FROM kb_2")
total_count = cur.fetchone()[0]
print(f"\n总记录数: {total_count}")

# 检查是否有重复的text字段
cur.execute("""
    SELECT text, COUNT(*) as cnt 
    FROM kb_2 
    GROUP BY text 
    HAVING COUNT(*) > 1 
    ORDER BY cnt DESC
    LIMIT 10
""")
duplicates = cur.fetchall()

print(f"\n重复的text记录:")
if duplicates:
    for text, cnt in duplicates:
        print(f"  重复次数: {cnt}, 内容预览: {text[:80]}...")
else:
    print("  无重复记录")

# 检查segment_id的分布
cur.execute("""
    SELECT (metadata->>'segment_id')::int as segment_id, COUNT(*) as cnt 
    FROM kb_2 
    GROUP BY segment_id 
    HAVING COUNT(*) > 1 
    ORDER BY cnt DESC
    LIMIT 10
""")
segment_duplicates = cur.fetchall()

print(f"\n重复的segment_id:")
if segment_duplicates:
    for seg_id, cnt in segment_duplicates:
        print(f"  segment_id={seg_id}, 重复次数={cnt}")
else:
    print("  无重复的segment_id")

# 查看segment_id=275的所有记录
cur.execute("""
    SELECT id, text, metadata, embedding 
    FROM kb_2 
    WHERE (metadata->>'segment_id')::int = 275
""")
records_275 = cur.fetchall()

print(f"\nsegment_id=275的记录数: {len(records_275)}")
for i, (rec_id, text, metadata, embedding) in enumerate(records_275):
    meta = json.loads(metadata) if isinstance(metadata, str) else metadata
    print(f"\n  记录{i+1}: id={rec_id}, metadata={meta}")
    print(f"    text长度: {len(text)}")
    print(f"    embedding长度: {len(embedding) if embedding else 0}")

# 检查document_id的分布
cur.execute("""
    SELECT (metadata->>'document_id')::int as document_id, COUNT(*) as cnt 
    FROM kb_2 
    GROUP BY document_id 
    ORDER BY cnt DESC
    LIMIT 5
""")
doc_dist = cur.fetchall()

print(f"\ndocument_id分布:")
for doc_id, cnt in doc_dist:
    print(f"  document_id={doc_id}, 记录数={cnt}")

conn.close()
print("\n检查完成！")