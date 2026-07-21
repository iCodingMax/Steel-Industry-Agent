"""
检查PGVectorStore创建的表结构
"""
import psycopg

conn = psycopg.connect(
    host='localhost',
    port=5432,
    dbname='steel_agent',
    user='postgres',
    password='postgres'
)

cur = conn.cursor()

# 查看所有表
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = cur.fetchall()
print("所有表:")
for table, in tables:
    print(f"  {table}")

# 检查是否有pgvector相关的表
print("\n检查pgvector相关的表:")
for table, in tables:
    if 'kb_' in table.lower():
        print(f"\n表: {table}")
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  记录数: {count}")
        
        # 查看前5条记录
        cur.execute(f"SELECT * FROM {table} LIMIT 5")
        rows = cur.fetchall()
        if rows:
            # 获取列名
            col_names = [desc[0] for desc in cur.description]
            print(f"  列名: {col_names}")
            for i, row in enumerate(rows):
                print(f"\n  记录{i+1}:")
                for col_name, val in zip(col_names, row):
                    if col_name == 'embedding':
                        print(f"    {col_name}: 向量长度={len(val) if val else 0}")
                    elif col_name == 'metadata':
                        print(f"    {col_name}: {val}")
                    else:
                        print(f"    {col_name}: {val}")

conn.close()