"""
测试NL2SQL Schema筛选优化效果
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.nl2sql_service import NL2SQLEngine, SchemaLinkingEngine
from app.core.database import SystemAsyncSession
from app.models.datasource import TableSchema
import json


async def test_smart_filter():
    """测试智能表筛选"""
    print("=" * 80)
    print("测试智能表筛选功能")
    print("=" * 80)
    
    # 模拟表结构数据
    class MockSchema:
        def __init__(self, table_name, table_comment, columns):
            self.table_name = table_name
            self.table_comment = table_comment
            self.columns = json.dumps(columns)
    
    mock_schemas = [
        MockSchema("bof_act_heat_add", "转炉生产表", [{"name": "id", "type": "bigint"}]),
        MockSchema("bof_act_add_sum_add", "转炉加料表", [{"name": "id", "type": "bigint"}]),
        MockSchema("cc_heat_report_add", "连铸生产表", [{"name": "id", "type": "bigint"}]),
        MockSchema("lf_act_heat_add", "精炼LF炉生产表", [{"name": "id", "type": "bigint"}]),
        MockSchema("rh_act_heat_add", "精炼RH炉生产表", [{"name": "id", "type": "bigint"}]),
        MockSchema("hgbf1_expert_lab_ingredient", "矿石化验数据", [{"name": "id", "type": "bigint"}]),
    ]
    
    # 测试用例
    test_cases = [
        ("转炉昨天生产了多少炉钢？", ["bof_act_heat_add", "bof_act_add_sum_add"]),
        ("连铸机的生产情况如何？", ["cc_heat_report_add"]),
        ("精炼LF炉的温度数据", ["lf_act_heat_add", "lf_act_add_sum_add"]),
        ("矿石的化验成分数据", ["hgbf1_expert_lab_ingredient"]),
        ("hello", []),  # 不相关的问题
        ("统计今天的生产数据", ["bof_act_heat_add", "cc_heat_report_add", "lf_act_heat_add", "rh_act_heat_add", "hgbf1_l2_report_hour"]),
    ]
    
    for question, expected_tables in test_cases:
        result = NL2SQLEngine._smart_table_filter(question, mock_schemas)
        result_tables = [s.table_name for s in result]
        
        print(f"\n问题: {question}")
        print(f"  期望表: {expected_tables}")
        print(f"  实际表: {result_tables}")
        print(f"  筛选效果: {len(mock_schemas)} -> {len(result)} 表")
        
        # 检查是否包含期望的表
        if expected_tables:
            matched = any(t in result_tables for t in expected_tables)
            print(f"  [OK] 匹配成功" if matched else "  [FAIL] 匹配失败")
        else:
            print(f"  [INFO] 无需匹配（返回全部表）")


async def test_schema_linking():
    """测试Schema Linking"""
    print("\n" + "=" * 80)
    print("测试Schema Linking功能")
    print("=" * 80)
    
    async with SystemAsyncSession() as db:
        # 测试用例
        test_cases = [
            "转炉昨天生产了多少炉钢？",
            "连铸机的生产情况",
            "精炼炉的温度数据",
        ]
        
        for question in test_cases:
            try:
                links = await SchemaLinkingEngine.link(db, question, datasource_id=8)
                linked_tables = [link[0] for link in links]
                
                print(f"\n问题: {question}")
                print(f"  相关表: {linked_tables}")
                print(f"  [OK] Schema Linking成功")
            except Exception as e:
                print(f"\n问题: {question}")
                print(f"  [FAIL] Schema Linking失败: {e}")


async def test_prompt_size():
    """测试优化后的Prompt大小"""
    print("\n" + "=" * 80)
    print("测试优化后的Prompt大小")
    print("=" * 80)
    
    async with SystemAsyncSession() as db:
        # 获取数据源8的表结构
        from sqlalchemy import select
        stmt = select(TableSchema).where(TableSchema.datasource_id == 8)
        result = await db.execute(stmt)
        all_schemas = [s for s in result.scalars().all() if s.table_name not in NL2SQLEngine.SYSTEM_TABLES]
        
        print(f"\n原始表数量: {len(all_schemas)}")
        
        # 测试不同问题的筛选效果
        test_questions = [
            "转炉昨天生产了多少炉钢？",
            "连铸机的生产情况如何？",
            "hello",  # 不相关问题
        ]
        
        for question in test_questions:
            # 应用智能筛选
            filtered = NL2SQLEngine._smart_table_filter(question, all_schemas)
            
            # 计算Prompt大小
            schema_desc = []
            for schema in filtered:
                columns = json.loads(schema.columns) if schema.columns else []
                col_info = []
                for col in columns:
                    col_type = col['type']
                    col_comment = col.get('comment', '') or col.get('remarks', '') or ''
                    if col_comment:
                        col_info.append(f"{col['name']}({col_type}) COMMENT '{col_comment}'")
                    else:
                        col_info.append(f"{col['name']}({col_type})")
                schema_desc.append(f"CREATE TABLE {schema.table_name} ({', '.join(col_info)})")
            
            schema_text = "\n".join(schema_desc)
            prompt_size = len(schema_text)
            estimated_tokens = prompt_size // 4
            
            print(f"\n问题: {question}")
            print(f"  筛选后表数量: {len(filtered)} / {len(all_schemas)}")
            print(f"  Prompt字符数: {prompt_size}")
            print(f"  估算Token数: {estimated_tokens}")
            print(f"  Token减少: {100 * (1 - estimated_tokens / 12031):.1f}%")


async def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("NL2SQL Schema优化测试")
    print("=" * 80)
    
    # 测试智能筛选
    await test_smart_filter()
    
    # 测试Schema Linking
    await test_schema_linking()
    
    # 测试Prompt大小
    await test_prompt_size()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())