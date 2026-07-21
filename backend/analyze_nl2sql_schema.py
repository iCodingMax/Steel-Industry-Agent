"""
分析NL2SQL流程中涉及的Schema
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

# 1. 获取所有表结构
cur.execute("""
    SELECT id, datasource_id, table_name, table_comment, columns 
    FROM table_schemas 
    ORDER BY id
""")

all_tables = cur.fetchall()

print("=" * 80)
print(f"系统表结构总览")
print("=" * 80)
print(f"总表数量: {len(all_tables)}")

# 2. NL2SQL中定义的系统内部表（会被过滤）
SYSTEM_TABLES = {
    "users", "sessions", "messages", "datasources", "table_schemas",
    "metrics", "dimensions", "terms", "knowledge_bases", "documents",
    "document_segments", "llm_configs",
}

print(f"\n系统内部表（会被过滤）: {SYSTEM_TABLES}")

# 3. 分析业务表
print("\n" + "=" * 80)
print(f"NL2SQL可用的业务表详情")
print("=" * 80)

business_tables = []
total_columns = 0
table_details = []

for row in all_tables:
    table_id, datasource_id, table_name, table_comment, columns_json = row
    
    # 过滤系统表
    if table_name in SYSTEM_TABLES:
        continue
    
    # 解析字段信息
    columns = columns_json if isinstance(columns_json, list) else json.loads(columns_json) if columns_json else []
    total_columns += len(columns)
    
    # 收集字段详情
    col_details = []
    for col in columns:
        col_name = col.get('name', '')
        col_type = col.get('type', '')
        col_comment = col.get('comment', '') or col.get('remarks', '')
        col_details.append({
            'name': col_name,
            'type': col_type,
            'comment': col_comment
        })
    
    business_tables.append(table_name)
    table_details.append({
        'id': table_id,
        'datasource_id': datasource_id,
        'table_name': table_name,
        'table_comment': table_comment or '',
        'column_count': len(columns),
        'columns': col_details
    })

print(f"\n业务表总数: {len(business_tables)}")
print(f"业务字段总数: {total_columns}")

# 4. 按数据源分组
print("\n" + "=" * 80)
print(f"按数据源分组")
print("=" * 80)

datasource_tables = {}
for t in table_details:
    ds_id = t['datasource_id']
    if ds_id not in datasource_tables:
        datasource_tables[ds_id] = []
    datasource_tables[ds_id].append(t)

for ds_id, tables in datasource_tables.items():
    print(f"\n数据源 ID={ds_id}: {len(tables)} 张表")
    for t in tables:
        print(f"  - {t['table_name']} ({t['column_count']} 字段): {t['table_comment']}")

# 5. 输出详细的表结构信息
print("\n" + "=" * 80)
print(f"详细表结构信息")
print("=" * 80)

for t in table_details:
    print(f"\n表 {t['table_name']} (ID={t['id']}, 数据源={t['datasource_id']}): {t['table_comment']}")
    print(f"  字段数: {t['column_count']}")
    print("  字段列表:")
    for col in t['columns'][:10]:  # 只显示前10个字段
        comment = f" -- {col['comment']}" if col['comment'] else ""
        print(f"    - {col['name']} ({col['type']}){comment}")
    if len(t['columns']) > 10:
        print(f"    ... 还有 {len(t['columns']) - 10} 个字段")

# 6. 计算NL2SQL Prompt大小
print("\n" + "=" * 80)
print(f"NL2SQL Prompt 大小估算")
print("=" * 80)

schema_desc = []
for t in table_details:
    col_info = []
    for col in t['columns']:
        col_type = col['type']
        col_comment = col['comment']
        if col_comment:
            col_info.append(f"{col['name']}({col_type}) COMMENT '{col_comment}'")
        else:
            col_info.append(f"{col['name']}({col_type})")
    schema_desc.append(f"CREATE TABLE {t['table_name']} ({', '.join(col_info)})")

schema_text = "\n".join(schema_desc)

prompt_template = """你是一个SQL专家，请根据用户问题和数据库Schema生成正确的SQL查询语句。

## 数据库Schema：
{schema_text}

## 用户问题：
{question}

## SQL生成要求：
1. 根据问题从数据库中获取所需信息
2. 使用正确的表名和字段名
3. 添加必要的过滤条件
4. 为查询字段添加中文别名（AS子句），别名使用字段COMMENT中的中文名称
5. 只返回纯SQL语句，不要包含markdown代码块标记或解释文字

请直接返回SQL语句："""

prompt = prompt_template.format(schema_text=schema_text, question="{question}")

print(f"Schema部分字符数: {len(schema_text)}")
print(f"完整Prompt字符数: {len(prompt)}")
print(f"估算Token数: {len(prompt) // 4}")

conn.close()

print("\n分析完成！")