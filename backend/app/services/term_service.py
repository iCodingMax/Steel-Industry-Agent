"""
术语服务模块
管理钢铁行业术语的CRUD操作和搜索

主要功能：
1. 术语管理：创建、查询、更新、删除术语
2. 术语搜索：支持按名称和代码搜索
3. 代码唯一性校验：确保术语代码不重复

术语数据结构：
- term: 术语名称（中文）
- code: 术语代码（唯一标识）
- definition: 术语定义/解释
- category: 术语分类（如工艺、设备、质量等）
- synonyms: 同义词列表（JSON格式）
- related_terms: 相关术语列表（JSON格式）
"""
import json
from typing import List, Optional
from sqlalchemy import select
from loguru import logger

from app.models.term import Term
from app.schemas.term import TermCreate, TermUpdate
from app.middlewares.exception_handler import BusinessException


class TermService:
    """
    术语服务类
    负责钢铁行业术语的生命周期管理
    支持术语的创建、查询、更新、删除和搜索
    """

    @staticmethod
    async def create(db, data: TermCreate) -> Term:
        """
        创建术语

        :param db: 数据库会话
        :param data: 术语创建参数
        :return: 创建的术语对象
        :raises BusinessException: 术语代码已存在时抛出
        """
        logger.debug(f"创建术语: term={data.term}, code={data.code}")

        # 校验代码唯一性
        existing = await TermService.get_by_code(db, data.code)
        if existing:
            raise BusinessException(code=400, message=f"术语代码已存在: {data.code}")

        term = Term(
            term=data.term,
            code=data.code,
            definition=data.definition,
            category=data.category,
            synonyms=json.dumps(data.synonyms, ensure_ascii=False) if data.synonyms else None,
            datasource_id=data.datasourceId,
            related_terms=json.dumps(data.relatedTerms, ensure_ascii=False) if data.relatedTerms else None,
        )
        db.add(term)
        await db.commit()
        await db.refresh(term)
        logger.info(f"创建术语成功: {term.term} (ID: {term.id})")
        return term

    @staticmethod
    async def get_by_id(db, term_id: int) -> Optional[Term]:
        """
        根据ID获取术语

        :param db: 数据库会话
        :param term_id: 术语ID
        :return: 术语对象（不存在返回None）
        """
        stmt = select(Term).where(Term.id == term_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db, code: str) -> Optional[Term]:
        """
        根据代码获取术语

        :param db: 数据库会话
        :param code: 术语代码
        :return: 术语对象（不存在返回None）
        """
        stmt = select(Term).where(Term.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[Term]:
        """
        获取所有术语

        :param db: 数据库会话
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数）
        :return: 术语列表
        """
        stmt = select(Term).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search(db, keyword: str) -> List[Term]:
        """
        搜索术语（按名称或代码）

        :param db: 数据库会话
        :param keyword: 搜索关键词
        :return: 匹配的术语列表（最多50条）
        """
        stmt = select(Term).where(
            (Term.term.contains(keyword)) | (Term.code.contains(keyword))
        ).limit(50)
        result = await db.execute(stmt)
        terms = list(result.scalars().all())
        logger.debug(f"术语搜索完成: keyword={keyword}, 数量={len(terms)}")
        return terms

    @staticmethod
    async def update(db, term_id: int, data: TermUpdate) -> Optional[Term]:
        """
        更新术语

        :param db: 数据库会话
        :param term_id: 术语ID
        :param data: 更新参数（仅包含需要更新的字段）
        :return: 更新后的术语对象
        :raises BusinessException: 术语不存在或代码重复时抛出
        """
        term = await TermService.get_by_id(db, term_id)
        if not term:
            raise BusinessException(code=404, message="术语不存在")

        # 如果代码被修改，校验新代码唯一性
        if data.code and data.code != term.code:
            existing = await TermService.get_by_code(db, data.code)
            if existing:
                raise BusinessException(code=400, message=f"术语代码已存在: {data.code}")

        update_data = data.model_dump(exclude_unset=True)
        if "synonyms" in update_data and update_data["synonyms"]:
            update_data["synonyms"] = json.dumps(update_data["synonyms"], ensure_ascii=False)
        if "relatedTerms" in update_data and update_data["relatedTerms"]:
            update_data["relatedTerms"] = json.dumps(update_data["relatedTerms"], ensure_ascii=False)
        for key, value in update_data.items():
            if hasattr(term, key):
                setattr(term, key, value)

        await db.commit()
        await db.refresh(term)
        logger.info(f"更新术语成功: {term.term} (ID: {term.id})")
        return term

    @staticmethod
    async def delete(db, term_id: int) -> None:
        """
        删除术语

        :param db: 数据库会话
        :param term_id: 术语ID
        :raises BusinessException: 术语不存在时抛出
        """
        term = await TermService.get_by_id(db, term_id)
        if not term:
            raise BusinessException(code=404, message="术语不存在")

        await db.delete(term)
        await db.commit()
        logger.info(f"删除术语成功: {term.term} (ID: {term_id})")


# 服务实例
term_service = TermService()
logger.info("术语服务实例已创建")
