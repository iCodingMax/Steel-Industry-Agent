"""
转炉炼钢示例数据初始化脚本

使用方式：
    cd backend
    python seed_data.py

功能：
    1. 创建转炉炼钢示例数据源
    2. 初始化指标、维度、术语数据
    3. 自动同步数据源表结构
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import MySQLAsyncSession, init_db
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.dimension import Dimension
from app.models.term import Term
from sqlalchemy import select


# ==================== 转炉炼钢示例数据 ====================

DATASOURCE_DATA = {
    "name": "转炉炼钢生产数据库",
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "database": "steel_agent",
    "username": "root",
    "password": "@Maxwell@2024",
    "charset": "utf8mb4",
    "description": "转炉炼钢生产过程数据，包含炉次信息、原料消耗、吹炼参数、钢水成分等",
    "status": "active",
}

METRICS_DATA = [
    # ---- 生产产量指标 ----
    {
        "name": "转炉钢产量",
        "code": "converter_steel_output",
        "description": "统计时间段内转炉产钢总量（吨）",
        "sql_expression": "SELECT SUM(steel_weight) AS total_output FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "number",
        "unit": "吨",
        "group_name": "生产产量",
        "tags": '["产量", "转炉", "核心指标"]',
    },
    {
        "name": "平均炉产钢量",
        "code": "avg_heat_weight",
        "description": "每炉平均产钢量（吨/炉）",
        "sql_expression": "SELECT AVG(steel_weight) AS avg_weight FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "number",
        "unit": "吨/炉",
        "group_name": "生产产量",
        "tags": '["产量", "转炉"]',
    },
    {
        "name": "冶炼炉数",
        "code": "heat_count",
        "description": "统计时间段内冶炼总炉数",
        "sql_expression": "SELECT COUNT(*) AS heat_count FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "number",
        "unit": "炉",
        "group_name": "生产产量",
        "tags": '["产量", "转炉"]',
    },
    # ---- 原料消耗指标 ----
    {
        "name": "钢铁料消耗",
        "code": "steel_material_consumption",
        "description": "每吨钢水的钢铁料消耗量（kg/t）",
        "sql_expression": "SELECT AVG(iron_weight + scrap_weight) / AVG(steel_weight) * 1000 AS consumption FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "number",
        "unit": "kg/t",
        "group_name": "原料消耗",
        "tags": '["消耗", "核心指标"]',
    },
    {
        "name": "平均铁水比",
        "code": "hot_metal_ratio",
        "description": "铁水占钢铁料的比例",
        "sql_expression": "SELECT AVG(iron_weight) / AVG(iron_weight + scrap_weight) * 100 AS ratio FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "percent",
        "unit": "%",
        "group_name": "原料消耗",
        "tags": '["消耗", "配比"]',
    },
    {
        "name": "石灰消耗",
        "code": "lime_consumption",
        "description": "每吨钢水的石灰消耗量（kg/t）",
        "sql_expression": "SELECT AVG(lime_weight) / AVG(steel_weight) * 1000 AS consumption FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "number",
        "unit": "kg/t",
        "group_name": "原料消耗",
        "tags": '["消耗", "造渣"]',
    },
    # ---- 冶炼效率指标 ----
    {
        "name": "平均冶炼周期",
        "code": "avg_tap_to_tap",
        "description": "从装料到出钢的平均时间（分钟）",
        "sql_expression": "SELECT AVG(TIMESTAMPDIFF(MINUTE, heat_start_time, tap_time)) AS avg_duration FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}' AND tap_time IS NOT NULL",
        "result_type": "number",
        "unit": "分钟",
        "group_name": "冶炼效率",
        "tags": '["效率", "核心指标"]',
    },
    {
        "name": "平均吹炼时间",
        "code": "avg_blowing_time",
        "description": "纯吹氧时间（分钟）",
        "sql_expression": "SELECT AVG(blowing_time) AS avg_time FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "number",
        "unit": "分钟",
        "group_name": "冶炼效率",
        "tags": '["效率", "吹炼"]',
    },
    # ---- 质量指标 ----
    {
        "name": "终点命中达标率",
        "code": "endpoint_hit_rate",
        "description": "终点温度和碳同时命中的炉次占比",
        "sql_expression": "SELECT SUM(CASE WHEN endpoint_hit = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100 AS hit_rate FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}'",
        "result_type": "percent",
        "unit": "%",
        "group_name": "质量指标",
        "tags": '["质量", "核心指标"]',
    },
    {
        "name": "平均终点温度",
        "code": "avg_endpoint_temp",
        "description": "终点钢水温度平均值（℃）",
        "sql_expression": "SELECT AVG(endpoint_temperature) AS avg_temp FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}' AND endpoint_temperature IS NOT NULL",
        "result_type": "number",
        "unit": "℃",
        "group_name": "质量指标",
        "tags": '["质量", "温度"]',
    },
    {
        "name": "平均终点碳",
        "code": "avg_endpoint_carbon",
        "description": "终点钢水碳含量平均值（%）",
        "sql_expression": "SELECT AVG(endpoint_carbon) AS avg_carbon FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}' AND endpoint_carbon IS NOT NULL",
        "result_type": "number",
        "unit": "%",
        "group_name": "质量指标",
        "tags": '["质量", "成分"]',
    },
    # ---- 氧气消耗指标 ----
    {
        "name": "氧气消耗",
        "code": "oxygen_consumption",
        "description": "每吨钢水的氧气消耗量（Nm³/t）",
        "sql_expression": "SELECT AVG(oxygen_volume) / AVG(steel_weight) AS consumption FROM converter_heats WHERE heat_start_time >= '{start_date}' AND heat_start_time <= '{end_date}' AND oxygen_volume IS NOT NULL",
        "result_type": "number",
        "unit": "Nm³/t",
        "group_name": "能源消耗",
        "tags": '["消耗", "能源"]',
    },
]

DIMENSIONS_DATA = [
    # ---- 时间维度 ----
    {
        "name": "冶炼日期",
        "code": "heat_date",
        "description": "冶炼发生的日期",
        "table_name": "converter_heats",
        "column_name": "heat_start_time",
        "data_type": "date",
        "level": 1,
    },
    # ---- 组织维度 ----
    {
        "name": "转炉编号",
        "code": "converter_id",
        "description": "转炉设备编号（如1#、2#、3#转炉）",
        "table_name": "converter_heats",
        "column_name": "converter_no",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "班组",
        "code": "shift_group",
        "description": "生产班组（甲班/乙班/丙班/丁班）",
        "table_name": "converter_heats",
        "column_name": "shift_group",
        "data_type": "string",
        "level": 1,
    },
    # ---- 钢种维度 ----
    {
        "name": "钢种",
        "code": "steel_grade",
        "description": "冶炼的钢种牌号（如Q235B、HRB400等）",
        "table_name": "converter_heats",
        "column_name": "steel_grade",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "钢种系列",
        "code": "steel_series",
        "description": "钢种大类（如碳结钢、低合金钢、优碳钢等）",
        "table_name": "converter_heats",
        "column_name": "steel_series",
        "data_type": "string",
        "level": 1,
    },
    # ---- 工艺维度 ----
    {
        "name": "吹炼模式",
        "code": "blowing_mode",
        "description": "吹炼方式（单渣法/双渣法/复吹）",
        "table_name": "converter_heats",
        "column_name": "blowing_mode",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "终点命中状态",
        "code": "endpoint_hit",
        "description": "终点温度碳是否同时命中",
        "table_name": "converter_heats",
        "column_name": "endpoint_hit",
        "data_type": "string",
        "level": 1,
    },
]

TERMS_DATA = [
    # ---- 工艺术语 ----
    {
        "term": "转炉炼钢",
        "code": "converter_steelmaking",
        "definition": "利用转炉倾斜旋转吹氧将铁水中碳、硅、锰、磷等杂质氧化去除，炼出合格钢水的冶炼工艺",
        "category": "工艺",
        "synonyms": '["转炉", "LD转炉", "氧气转炉", "碱性氧气转炉"]',
        "related_terms": '["吹炼", "终点控制", "造渣"]',
    },
    {
        "term": "吹炼",
        "code": "blowing",
        "definition": "向转炉熔池吹入氧气（或氧气+惰性气体），使铁水中杂质氧化升温的过程",
        "category": "工艺",
        "synonyms": '["吹氧", "氧气吹炼", "氧化吹炼"]',
        "related_terms": '["转炉炼钢", "吹炼时间", "氧枪"]',
    },
    {
        "term": "终点控制",
        "code": "endpoint_control",
        "definition": "在吹炼结束时使钢水温度和成分同时达到目标值的操作控制技术",
        "category": "工艺",
        "synonyms": '["终点命中", "拉碳", "一次倒炉命中"]',
        "related_terms": '["终点温度", "终点碳", "补吹"]',
    },
    {
        "term": "造渣",
        "code": "slag_making",
        "definition": "通过加入石灰、萤石等造渣剂，在熔池表面形成覆盖渣层，吸附脱除磷硫等杂质的过程",
        "category": "工艺",
        "synonyms": '["成渣", "造渣制度", "碱性渣"]',
        "related_terms": '["石灰", "渣量", "脱磷", "脱硫"]',
    },
    {
        "term": "补吹",
        "code": "reblow",
        "definition": "倒炉取样化验后，因终点温度或碳含量未达标而再次吹氧调整的操作",
        "category": "工艺",
        "synonyms": '["二次吹炼", "再吹", "后吹"]',
        "related_terms": '["终点控制", "终点命中"]',
    },
    # ---- 原料术语 ----
    {
        "term": "铁水",
        "code": "hot_metal",
        "definition": "高炉冶炼产出的液态生铁，温度约1300-1450℃，含碳3-4.5%，是转炉炼钢的主要原料",
        "category": "原料",
        "synonyms": '["热金属", "液态生铁", "高炉铁水"]',
        "related_terms": '["铁水比", "铁水预处理", "废钢"]',
    },
    {
        "term": "废钢",
        "code": "scrap_steel",
        "definition": "回收的废旧钢材，作为转炉炼钢的冷却剂和金属料补充",
        "category": "原料",
        "synonyms": '["返回废钢", "冷料", "钢铁料"]',
        "related_terms": '["铁水", "钢铁料消耗", "废钢比"]',
    },
    {
        "term": "石灰",
        "code": "lime",
        "definition": "主要成分为CaO的造渣剂，用于脱磷脱硫、提高炉渣碱度",
        "category": "原料",
        "synonyms": '["生石灰", "氧化钙", "活性石灰"]',
        "related_terms": '["造渣", "碱度", "石灰消耗"]',
    },
    # ---- 质量术语 ----
    {
        "term": "钢水成分",
        "code": "molten_steel_composition",
        "definition": "钢水中C、Si、Mn、P、S等元素的含量，是衡量钢水质量的重要指标",
        "category": "质量",
        "synonyms": '["化学成分", "钢种成分", "熔炼成分"]',
        "related_terms": '["终点碳", "终点温度", "钢种"]',
    },
    {
        "term": "终点温度",
        "code": "endpoint_temperature",
        "definition": "吹炼结束时熔池中钢水的温度，通常控制在1600-1700℃范围",
        "category": "质量",
        "synonyms": '["出钢温度", "倒炉温度", "熔池温度"]',
        "related_terms": '["终点控制", "终点碳", "温度命中"]',
    },
    {
        "term": "终点碳",
        "code": "endpoint_carbon",
        "definition": "吹炼结束时钢水中的碳含量，是判断冶炼是否达标的关键参数",
        "category": "质量",
        "synonyms": '["终点C", "出钢碳", "熔池碳含量"]',
        "related_terms": '["终点控制", "终点温度", "碳命中"]',
    },
    # ---- 设备术语 ----
    {
        "term": "氧枪",
        "code": "oxygen_lance",
        "definition": "向转炉熔池吹入高压氧水的水冷喷枪，是转炉核心设备",
        "category": "设备",
        "synonyms": '["吹氧管", "喷枪", "氧枪喷头"]',
        "related_terms": '["吹炼", "氧枪寿命", "枪位"]',
    },
    {
        "term": "炉龄",
        "code": "converter_campaign_life",
        "definition": "转炉炉衬从开始使用到需要更换期间所炼钢的炉次数，是衡量耐火材料寿命的关键指标",
        "category": "设备",
        "synonyms": '["转炉寿命", "炉衬寿命", "campaign"]',
        "related_terms": '["溅渣护炉", "耐火材料", "补炉"]',
    },
    {
        "term": "溅渣护炉",
        "code": "slag_splashing",
        "definition": "出钢后利用高压氮气将炉渣溅射到炉衬表面形成保护层，延长炉衬寿命的技术",
        "category": "设备",
        "synonyms": '["溅渣", "氮气溅渣", "护炉"]',
        "related_terms": '["炉龄", "炉衬", "耐火材料"]',
    },
    # ---- 生产管理术语 ----
    {
        "term": "冶炼周期",
        "code": "tap_to_tap_time",
        "definition": "从上一炉出钢完毕到下一炉出钢完毕的总时间，包括装料、吹炼、出钢等全部工序",
        "category": "管理",
        "synonyms": '["炉到炉时间", "冶炼时间", "T-T时间"]',
        "related_terms": '["吹炼时间", "生产节奏", "日历作业率"]',
    },
    {
        "term": "钢铁料消耗",
        "code": "steel_material_consumption",
        "definition": "生产每吨合格钢水所消耗的钢铁料总量（铁水+废钢），单位kg/t，是转炉最重要的技术经济指标",
        "category": "管理",
        "synonyms": '["金属料消耗", "原料消耗", "钢铁料收得率"]',
        "related_terms": '["铁水比", "废钢比", "收得率"]',
    },
    {
        "term": "钢种",
        "code": "steel_grade",
        "definition": "按化学成分和力学性能分类的钢材牌号，如Q235B、HRB400、45#等",
        "category": "管理",
        "synonyms": '["牌号", "钢号", "钢级"]',
        "related_terms": '["终点碳", "钢水成分", "合金化"]',
    },
]


async def seed():
    """初始化示例数据"""
    from loguru import logger

    # 初始化数据库表
    await init_db()

    async with MySQLAsyncSession() as db:
        # 1. 创建数据源
        ds_stmt = select(DataSource).where(DataSource.name == "转炉炼钢生产数据库")
        result = await db.execute(ds_stmt)
        ds = result.scalar_one_or_none()

        if ds:
            logger.info(f"数据源已存在: {ds.name} (ID={ds.id})，跳过创建")
        else:
            ds = DataSource(**DATASOURCE_DATA)
            db.add(ds)
            await db.flush()
            logger.info(f"创建数据源: {ds.name} (ID={ds.id})")

        datasource_id = ds.id

        # 2. 创建指标
        existing_metrics = await db.execute(select(Metric).where(Metric.datasource_id == datasource_id))
        if list(existing_metrics.scalars().all()):
            logger.info("指标数据已存在，跳过创建")
        else:
            for m in METRICS_DATA:
                metric = Metric(datasource_id=datasource_id, **m)
                db.add(metric)
            logger.info(f"创建 {len(METRICS_DATA)} 条指标数据")

        # 3. 创建维度
        existing_dims = await db.execute(select(Dimension).where(Dimension.datasource_id == datasource_id))
        if list(existing_dims.scalars().all()):
            logger.info("维度数据已存在，跳过创建")
        else:
            for d in DIMENSIONS_DATA:
                dim = Dimension(datasource_id=datasource_id, **d)
                db.add(dim)
            logger.info(f"创建 {len(DIMENSIONS_DATA)} 条维度数据")

        # 4. 创建术语
        existing_terms = await db.execute(select(Term).where(Term.datasource_id == datasource_id))
        if list(existing_terms.scalars().all()):
            logger.info("术语数据已存在，跳过创建")
        else:
            for t in TERMS_DATA:
                term = Term(datasource_id=datasource_id, **t)
                db.add(term)
            logger.info(f"创建 {len(TERMS_DATA)} 条术语数据")

        await db.commit()
        logger.success("示例数据初始化完成！")


if __name__ == "__main__":
    asyncio.run(seed())
