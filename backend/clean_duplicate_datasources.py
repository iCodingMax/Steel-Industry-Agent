"""
清理重复数据源和表结构记录
"""
import psycopg
from psycopg.rows import dict_row

# 连接PostgreSQL系统数据库
conn = psycopg.connect(
    host='localhost',
    port=5432,
    dbname='steel_agent',
    user='postgres',
    password='postgres',
    row_factory=dict_row
)

cur = conn.cursor()

print("=" * 80)
print("分析数据源重复情况")
print("=" * 80)

# 1. 查看所有数据源
cur.execute("""
    SELECT id, name, type, host, port, database, status, created_at
    FROM datasources
    ORDER BY id
""")
datasources = cur.fetchall()

print(f"\n当前数据源数量: {len(datasources)}")
for ds in datasources:
    print(f"  ID={ds['id']}: {ds['name']} ({ds['type']}://{ds['host']}:{ds['port']}/{ds['database']}) - {ds['status']}")

# 2. 分析每个数据源的表数量
print("\n" + "=" * 80)
print("各数据源的表结构数量")
print("=" * 80)

cur.execute("""
    SELECT datasource_id, COUNT(*) as table_count
    FROM table_schemas
    GROUP BY datasource_id
    ORDER BY datasource_id
""")
table_counts = cur.fetchall()

for tc in table_counts:
    print(f"  数据源 ID={tc['datasource_id']}: {tc['table_count']} 张表")

# 3. 检查重复的表结构（相同表名、相同数据库名）
print("\n" + "=" * 80)
print("检查重复的表结构")
print("=" * 80)

cur.execute("""
    SELECT table_name, COUNT(*) as count
    FROM table_schemas ts
    JOIN datasources d ON ts.datasource_id = d.id
    GROUP BY table_name
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
""")
duplicate_tables = cur.fetchall()

print(f"\n重复的表名数量: {len(duplicate_tables)}")
for dt in duplicate_tables[:10]:
    print(f"  {dt['table_name']}: 出现 {dt['count']} 次")

# 4. 找出应该保留的数据源（钢铁行业生产数据库）
print("\n" + "=" * 80)
print("确定保留的数据源")
print("=" * 80)

# 查找活跃的钢铁行业生产数据库
cur.execute("""
    SELECT id, name, database, status
    FROM datasources
    WHERE name LIKE '%钢铁%' OR name LIKE '%生产%'
    ORDER BY id DESC
""")
steel_datasources = cur.fetchall()

print(f"\n找到 {len(steel_datasources)} 个钢铁行业数据源")
for ds in steel_datasources:
    print(f"  ID={ds['id']}: {ds['name']} -> {ds['database']} ({ds['status']})")

# 5. 执行清理（保留ID最大的活跃数据源）
if len(steel_datasources) > 1:
    # 保留最后一个（ID最大）
    keep_id = steel_datasources[0]['id']
    delete_ids = [ds['id'] for ds in steel_datasources[1:]]
    
    print(f"\n将保留数据源 ID={keep_id}")
    print(f"将删除数据源 ID={delete_ids}")
    
    # 开始清理
    try:
        # 删除相关表结构
        for del_id in delete_ids:
            cur.execute("DELETE FROM table_schemas WHERE datasource_id = %s", (del_id,))
            print(f"  已删除数据源 ID={del_id} 的表结构")
        
        # 删除数据源
        for del_id in delete_ids:
            cur.execute("DELETE FROM datasources WHERE id = %s", (del_id,))
            print(f"  已删除数据源 ID={del_id}")
        
        conn.commit()
        print("\n✅ 清理完成！")
        
        # 显示清理后的结果
        cur.execute("SELECT COUNT(*) as count FROM datasources")
        total_ds = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) as count FROM table_schemas")
        total_tables = cur.fetchone()['count']
        print(f"\n清理后: {total_ds} 个数据源, {total_tables} 张表")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 清理失败: {e}")
else:
    print("\n无需清理，只有一个钢铁行业数据源")

conn.close()
print("\n分析完成！")