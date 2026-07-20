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

from app.core.database import SystemAsyncSession, init_db
from app.core.config import settings
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.dimension import Dimension
from app.models.term import Term
from sqlalchemy import select


# ==================== 转炉炼钢示例数据 ====================

DATASOURCE_DATA = {
    "name": "钢铁行业生产数据库",
    "type": "mysql",
    "host": settings.BUSINESS_DB_HOST or settings.MYSQL_HOST,
    "port": settings.BUSINESS_DB_PORT or settings.MYSQL_PORT,
    "database": settings.BUSINESS_DB_NAME,
    "username": settings.BUSINESS_DB_USER or settings.MYSQL_USER,
    "password": settings.BUSINESS_DB_PASSWORD or settings.MYSQL_PASSWORD,
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
        "sql_expression": "SELECT SUM(STEEL_WGT) AS total_output FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "number",
        "unit": "吨",
        "group_name": "生产产量",
        "tags": '["产量", "转炉", "核心指标"]',
    },
    {
        "name": "平均炉产钢量",
        "code": "avg_heat_weight",
        "description": "每炉平均产钢量（吨/炉）",
        "sql_expression": "SELECT AVG(STEEL_WGT) AS avg_weight FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "number",
        "unit": "吨/炉",
        "group_name": "生产产量",
        "tags": '["产量", "转炉"]',
    },
    {
        "name": "冶炼炉数",
        "code": "heat_count",
        "description": "统计时间段内冶炼总炉数",
        "sql_expression": "SELECT COUNT(*) AS heat_count FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
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
        "sql_expression": "SELECT AVG(IRON_WGT + SCRAP_WGT) / AVG(STEEL_WGT) * 1000 AS consumption FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "number",
        "unit": "kg/t",
        "group_name": "原料消耗",
        "tags": '["消耗", "核心指标"]',
    },
    {
        "name": "平均铁水比",
        "code": "hot_metal_ratio",
        "description": "铁水占钢铁料的比例",
        "sql_expression": "SELECT AVG(IRON_WGT) / AVG(IRON_WGT + SCRAP_WGT) * 100 AS ratio FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "percent",
        "unit": "%",
        "group_name": "原料消耗",
        "tags": '["消耗", "配比"]',
    },
    {
        "name": "造渣剂消耗",
        "code": "flux_consumption",
        "description": "每吨钢水的造渣剂消耗量（kg/t）",
        "sql_expression": "SELECT AVG(FLUX_WGT) / AVG(STEEL_WGT) * 1000 AS consumption FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "number",
        "unit": "kg/t",
        "group_name": "原料消耗",
        "tags": '["消耗", "造渣"]',
    },
    # ---- 冶炼效率指标 ----
    {
        "name": "平均冶炼周期",
        "code": "avg_smelt_cycle",
        "description": "从装料到出钢的平均冶炼时间（分钟）",
        "sql_expression": "SELECT AVG(SMELT_CYCLE) AS avg_duration FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "number",
        "unit": "分钟",
        "group_name": "冶炼效率",
        "tags": '["效率", "核心指标"]',
    },
    {
        "name": "每日吹炼次数",
        "code": "daily_blow_count",
        "description": "每日转炉吹炼总次数",
        "sql_expression": "SELECT DATE(PRODUCE_DATE) AS 生产日期, SUM(BLOW_COUNT) AS 每日吹炼次数 FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0 GROUP BY DATE(PRODUCE_DATE) ORDER BY 生产日期",
        "result_type": "number",
        "unit": "次",
        "group_name": "冶炼效率",
        "tags": '["效率", "吹炼"]',
    },
    # ---- 质量指标 ----
    {
        "name": "直接出钢率",
        "code": "direct_tap_rate",
        "description": "直接出钢（一次命中）的炉次占比",
        "sql_expression": "SELECT SUM(CASE WHEN IS_DIRECT_TAP = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100 AS hit_rate FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0",
        "result_type": "percent",
        "unit": "%",
        "group_name": "质量指标",
        "tags": '["质量", "核心指标"]',
    },
    {
        "name": "平均出钢温度",
        "code": "avg_tap_temp",
        "description": "出钢温度平均值（℃）",
        "sql_expression": "SELECT AVG(TAP_TEMP) AS avg_temp FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0 AND TAP_TEMP IS NOT NULL",
        "result_type": "number",
        "unit": "℃",
        "group_name": "质量指标",
        "tags": '["质量", "温度"]',
    },
    {
        "name": "平均终点碳",
        "code": "avg_endpoint_carbon",
        "description": "终点钢水碳含量平均值（%）",
        "sql_expression": "SELECT AVG(END_C) AS avg_carbon FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0 AND END_C IS NOT NULL",
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
        "sql_expression": "SELECT AVG(BLOW_O2_VOL) / AVG(STEEL_WGT) AS consumption FROM bof_act_heat_add WHERE PRODUCE_DATE >= '{start_date}' AND PRODUCE_DATE < '{end_date}' AND IS_DELETED = 0 AND BLOW_O2_VOL IS NOT NULL",
        "result_type": "number",
        "unit": "Nm³/t",
        "group_name": "能源消耗",
        "tags": '["消耗", "能源"]',
    },
    # ---- 炉况打分指标（hgbf1_condition_result） ----
    {
        "name": "每日炉况打分趋势",
        "code": "daily_condition_score_trend",
        "description": "按日期展示每日各打分项的平均打分值，适合折线图展示炉况变化趋势",
        "sql_expression": "SELECT DATE(SCORE_TIME) AS 日期, ITEM_NAME AS 打分项目, AVG(SCORE) AS 平均打分值 FROM hgbf1_condition_result WHERE SCORE_TIME >= '{start_date}' AND SCORE_TIME < '{end_date}' GROUP BY DATE(SCORE_TIME), ITEM_NAME ORDER BY 日期, ITEM_NAME",
        "result_type": "table",
        "unit": "分",
        "group_name": "炉况评价",
        "tags": '["炉况", "打分", "趋势"]',
    },
    {
        "name": "炉况综合得分",
        "code": "condition_total_score",
        "description": "指定时间段内各评分类型的平均综合得分",
        "sql_expression": "SELECT TYPE_CODE AS 评分类型, AVG(SCORE) AS 平均得分 FROM hgbf1_condition_result WHERE SCORE_TIME >= '{start_date}' AND SCORE_TIME < '{end_date}' GROUP BY TYPE_CODE ORDER BY 平均得分 DESC",
        "result_type": "table",
        "unit": "分",
        "group_name": "炉况评价",
        "tags": '["炉况", "综合", "得分"]',
    },
    {
        "name": "每日炉况综合得分趋势",
        "code": "daily_condition_total_score",
        "description": "按日期展示每日所有打分项的综合平均得分，适合折线图",
        "sql_expression": "SELECT DATE(SCORE_TIME) AS 日期, AVG(SCORE) AS 综合平均得分 FROM hgbf1_condition_result WHERE SCORE_TIME >= '{start_date}' AND SCORE_TIME < '{end_date}' GROUP BY DATE(SCORE_TIME) ORDER BY 日期",
        "result_type": "table",
        "unit": "分",
        "group_name": "炉况评价",
        "tags": '["炉况", "综合", "趋势"]',
    },
    {
        "name": "炉况打分明细",
        "code": "condition_score_detail",
        "description": "炉况打分结果的详细记录，包含打分时间、班次、打分项目、打分值、报告内容等",
        "sql_expression": "SELECT SCORE_TIME AS 打分时间, SCORE_SHIFT AS 班次, ITEM_CODE AS 打分项目代码, ITEM_NAME AS 打分项目名称, SCORE AS 打分值, PARENT_CODE AS 父项代码, TYPE_CODE AS 评分类型, REPORT_MSG AS 报告内容 FROM hgbf1_condition_result WHERE SCORE_TIME >= '{start_date}' AND SCORE_TIME < '{end_date}' ORDER BY SCORE_TIME LIMIT 1000",
        "result_type": "table",
        "unit": "",
        "group_name": "炉况评价",
        "tags": '["炉况", "明细", "打分"]',
    },
]

DIMENSIONS_DATA = [
    # ---- 时间维度 ----
    {
        "name": "冶炼日期",
        "code": "heat_date",
        "description": "冶炼发生的日期",
        "table_name": "bof_act_heat_add",
        "column_name": "PRODUCE_DATE",
        "data_type": "date",
        "level": 1,
    },
    # ---- 组织维度 ----
    {
        "name": "转炉编号",
        "code": "converter_id",
        "description": "转炉设备编号",
        "table_name": "bof_act_heat_add",
        "column_name": "PLANT_UNIT",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "班组",
        "code": "crew_id",
        "description": "生产班组",
        "table_name": "bof_act_heat_add",
        "column_name": "CREW_ID",
        "data_type": "string",
        "level": 1,
    },
    # ---- 钢种维度 ----
    {
        "name": "钢种",
        "code": "steel_grade",
        "description": "冶炼的钢种牌号（如Q235B、HRB400等）",
        "table_name": "bof_act_heat_add",
        "column_name": "STEEL_GRADE",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "精炼路线",
        "code": "refine_route",
        "description": "精炼工艺路线",
        "table_name": "bof_act_heat_add",
        "column_name": "REFINE_ROUTE",
        "data_type": "string",
        "level": 1,
    },
    # ---- 工艺维度 ----
    {
        "name": "是否单渣",
        "code": "is_dan_da",
        "description": "是否采用单渣法吹炼",
        "table_name": "bof_act_heat_add",
        "column_name": "IS_DAN_DA",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "是否直接出钢",
        "code": "is_direct_tap",
        "description": "终点是否直接出钢（一次命中）",
        "table_name": "bof_act_heat_add",
        "column_name": "IS_DIRECT_TAP",
        "data_type": "string",
        "level": 1,
    },
    # ---- 炉况打分维度（hgbf1_condition_result） ----
    {
        "name": "打分日期",
        "code": "score_date",
        "description": "炉况打分的日期",
        "table_name": "hgbf1_condition_result",
        "column_name": "SCORE_TIME",
        "data_type": "date",
        "level": 1,
    },
    {
        "name": "班次",
        "code": "score_shift",
        "description": "班次（1=白班, 2=中班, 3=夜班）",
        "table_name": "hgbf1_condition_result",
        "column_name": "SCORE_SHIFT",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "打分项目",
        "code": "item_name",
        "description": "炉况打分项目名称（如鼓风动能、发生趋势等）",
        "table_name": "hgbf1_condition_result",
        "column_name": "ITEM_NAME",
        "data_type": "string",
        "level": 1,
    },
    {
        "name": "评分类型",
        "code": "type_code",
        "description": "评分类型编码（如air、furnace、heat等）",
        "table_name": "hgbf1_condition_result",
        "column_name": "TYPE_CODE",
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
    # ---- 炉况评价术语 ----
    {
        "term": "炉况打分",
        "code": "condition_scoring",
        "definition": "对高炉运行状态进行量化评分的评价体系，涵盖鼓风、煤气、炉缸等多维度指标",
        "category": "炉况",
        "synonyms": '["炉况评价", "炉况评分", "炉况监测", "炉况报告"]',
        "related_terms": '["鼓风动能", "发生趋势", "炉缸活跃度"]',
    },
    {
        "term": "鼓风动能",
        "code": "blast_energy",
        "definition": "鼓风进入高炉风口时的动能，是衡量鼓风穿透能力的重要参数",
        "category": "炉况",
        "synonyms": '["鼓风", "风动能", "风口鼓风"]',
        "related_terms": '["炉况打分", "送风制度"]',
    },
    {
        "term": "炉缸活跃度",
        "code": "hearth_activity",
        "definition": "反映高炉炉缸工作状态的综合性指标，与铁水温度、渣铁排放等密切相关",
        "category": "炉况",
        "synonyms": '["炉缸", "炉缸状态", "炉底活跃"]',
        "related_terms": '["炉况打分", "铁水温度"]',
    },
]


async def seed():
    """初始化示例数据"""
    from loguru import logger

    # 初始化数据库表
    await init_db()

    async with SystemAsyncSession() as db:
        # 1. 确保唯一数据源存在且密码正确
        # 查找任何现有数据源（名称可能不同，但应该是唯一的业务数据源）
        all_ds_result = await db.execute(select(DataSource))
        all_ds_list = list(all_ds_result.scalars().all())

        if all_ds_list:
            # 取第一个（应该只有一个）
            ds = all_ds_list[0]
            # 如果有多余的数据源，删除
            for extra_ds in all_ds_list[1:]:
                logger.warning(f"删除多余数据源: {extra_ds.name} (ID={extra_ds.id})")
                await db.delete(extra_ds)
            # 更新连接信息（确保密码、数据库名正确）
            ds.name = "钢铁行业生产数据库"
            ds.type = "mysql"
            ds.host = settings.BUSINESS_DB_HOST or settings.MYSQL_HOST
            ds.port = settings.BUSINESS_DB_PORT or settings.MYSQL_PORT
            ds.database = settings.BUSINESS_DB_NAME
            ds.username = settings.BUSINESS_DB_USER or settings.MYSQL_USER
            ds.password = settings.BUSINESS_DB_PASSWORD or settings.MYSQL_PASSWORD
            ds.charset = "utf8mb4"
            ds.status = "active"
            logger.info(f"更新数据源: {ds.name} (ID={ds.id}), database={ds.database}")
            await db.flush()
        else:
            ds = DataSource(**DATASOURCE_DATA)
            db.add(ds)
            await db.flush()
            logger.info(f"创建数据源: {ds.name} (ID={ds.id})")

        datasource_id = ds.id

        # 2. 创建指标（按code去重，已存在则更新，不存在则插入，删除旧code）
        valid_metric_codes = [m["code"] for m in METRICS_DATA]
        stale_metrics = await db.execute(select(Metric).where(Metric.code.notin_(valid_metric_codes)))
        for sm in stale_metrics.scalars().all():
            logger.warning(f"删除旧指标: {sm.name} (code={sm.code})")
            await db.delete(sm)
        await db.flush()
        for m in METRICS_DATA:
            existing = await db.execute(select(Metric).where(Metric.code == m["code"]))
            existing_metric = existing.scalar_one_or_none()
            if existing_metric:
                for key, value in m.items():
                    setattr(existing_metric, key, value)
                existing_metric.datasource_id = datasource_id
            else:
                metric = Metric(datasource_id=datasource_id, **m)
                db.add(metric)
        await db.flush()
        logger.info(f"指标数据同步完成，共 {len(METRICS_DATA)} 条")

        # 3. 创建维度（按code去重，已存在则更新，不存在则插入，删除旧code）
        valid_dim_codes = [d["code"] for d in DIMENSIONS_DATA]
        stale_dims = await db.execute(select(Dimension).where(Dimension.code.notin_(valid_dim_codes)))
        for sd in stale_dims.scalars().all():
            logger.warning(f"删除旧维度: {sd.name} (code={sd.code})")
            await db.delete(sd)
        await db.flush()
        for d in DIMENSIONS_DATA:
            existing = await db.execute(select(Dimension).where(Dimension.code == d["code"]))
            existing_dim = existing.scalar_one_or_none()
            if existing_dim:
                for key, value in d.items():
                    setattr(existing_dim, key, value)
                existing_dim.datasource_id = datasource_id
            else:
                dim = Dimension(datasource_id=datasource_id, **d)
                db.add(dim)
        await db.flush()
        logger.info(f"维度数据同步完成，共 {len(DIMENSIONS_DATA)} 条")

        # 4. 创建术语（按code去重，已存在则更新，不存在则插入，删除旧code）
        valid_term_codes = [t["code"] for t in TERMS_DATA]
        stale_terms = await db.execute(select(Term).where(Term.code.notin_(valid_term_codes)))
        for st in stale_terms.scalars().all():
            logger.warning(f"删除旧术语: {st.term} (code={st.code})")
            await db.delete(st)
        await db.flush()
        for t in TERMS_DATA:
            existing = await db.execute(select(Term).where(Term.code == t["code"]))
            existing_term = existing.scalar_one_or_none()
            if existing_term:
                for key, value in t.items():
                    setattr(existing_term, key, value)
                existing_term.datasource_id = datasource_id
            else:
                term = Term(datasource_id=datasource_id, **t)
                db.add(term)
        await db.flush()
        logger.info(f"术语数据同步完成，共 {len(TERMS_DATA)} 条")

        await db.commit()

        # 5. 自动同步数据源Schema
        try:
            from app.services.datasource_service import DataSourceService
            schemas = await DataSourceService.sync_schema(db, datasource_id)
            await db.commit()
            logger.success(f"同步数据源Schema完成，共 {len(schemas)} 张表")
        except Exception as e:
            logger.warning(f"同步Schema失败（不影响其他数据）: {e}")

        logger.success("示例数据初始化完成！")


if __name__ == "__main__":
    asyncio.run(seed())
