import psycopg
import json

# 模拟NL2SQL生成Prompt的过程
conn = psycopg.connect('host=localhost port=5432 dbname=steel_agent user=postgres password=postgres')
cur = conn.cursor()
cur.execute('SELECT table_name, columns FROM table_schemas WHERE datasource_id = 8')

system_tables = {"users", "sessions", "messages", "datasources", "table_schemas",
                 "metrics", "dimensions", "terms", "knowledge_bases", "documents",
                 "document_segments", "llm_configs"}

schema_desc = []
for row in cur.fetchall():
    table_name = row[0]
    if table_name in system_tables:
        continue
    columns = row[1] if isinstance(row[1], list) else json.loads(row[1]) if row[1] else []
    col_info = []
    for col in columns:
        col_type = col['type']
        col_comment = col.get('comment', '') or col.get('remarks', '') or ''
        if col_comment:
            col_info.append(f"{col['name']}({col_type}) COMMENT '{col_comment}'")
        else:
            col_info.append(f"{col['name']}({col_type})")
    schema_desc.append(f"CREATE TABLE {table_name} ({', '.join(col_info)})")

schema_text = "\n".join(schema_desc)

# 计算Prompt大小
prompt_template = """你是一个SQL专家，请根据用户问题和数据库Schema生成正确的SQL查询语句。

## 数据库Schema：
{schema_text}

## 用户问题：
hello

## SQL生成要求：
1. 根据问题从数据库中获取所需信息
2. 使用正确的表名和字段名
3. 添加必要的过滤条件
4. 为查询字段添加中文别名（AS子句），别名使用字段COMMENT中的中文名称
5. 只返回纯SQL语句，不要包含markdown代码块标记或解释文字

请直接返回SQL语句："""

prompt = prompt_template.format(schema_text=schema_text)
print(f"Prompt字符数: {len(prompt)}")
print(f"Prompt Token数(估算): {len(prompt) // 4}")
print(f"Schema部分字符数: {len(schema_text)}")
print(f"表数量: {len(schema_desc)}")

conn.close()