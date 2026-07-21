"""
修复PostgreSQL自增序列与现有数据ID冲突问题
"""
import psycopg

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
print("检查messages表的ID和序列")
print("=" * 80)

# 1. 检查messages表的最大ID
cur.execute('SELECT MAX(id) FROM messages')
max_id = cur.fetchone()[0]
print(f"messages表最大ID: {max_id}")

# 2. 检查序列当前值
cur.execute("SELECT last_value FROM messages_id_seq")
seq_val = cur.fetchone()[0]
print(f"messages_id_seq序列当前值: {seq_val}")

# 3. 如果序列值小于最大ID，重置序列
if seq_val <= max_id:
    new_val = max_id + 1
    print(f"\n需要重置序列: {seq_val} -> {new_val}")
    cur.execute(f"ALTER SEQUENCE messages_id_seq RESTART WITH {new_val}")
    conn.commit()
    
    # 验证重置结果
    cur.execute("SELECT last_value FROM messages_id_seq")
    new_seq_val = cur.fetchone()[0]
    print(f"序列重置成功: {new_seq_val}")
else:
    print("\n序列值正常，无需重置")

# 4. 检查其他可能有问题的表
print("\n" + "=" * 80)
print("检查其他表的序列")
print("=" * 80)

tables_to_check = [
    'users', 'sessions', 'datasources', 'table_schemas',
    'metrics', 'dimensions', 'terms', 'knowledge_bases',
    'documents', 'document_segments', 'llm_configs'
]

for table in tables_to_check:
    try:
        # 获取最大ID
        cur.execute(f'SELECT MAX(id) FROM {table}')
        max_id = cur.fetchone()[0]
        
        # 获取序列当前值
        cur.execute(f"SELECT last_value FROM {table}_id_seq")
        seq_val = cur.fetchone()[0]
        
        print(f"\n{table}:")
        print(f"  最大ID: {max_id}")
        print(f"  序列值: {seq_val}")
        
        if max_id and seq_val <= max_id:
            new_val = max_id + 1
            print(f"  需要重置序列: {seq_val} -> {new_val}")
            cur.execute(f"ALTER SEQUENCE {table}_id_seq RESTART WITH {new_val}")
            conn.commit()
            print(f"  序列重置成功")
    except Exception as e:
        print(f"\n{table}: 检查失败 - {e}")

conn.close()
print("\n修复完成！")