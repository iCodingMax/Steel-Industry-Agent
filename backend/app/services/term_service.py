"""
术语服务
"""
import json
from typing import List, Optional
from sqlalchemy import select
from loguru import logger

from app.models.term import Term
from app.schemas.term import TermCreate, TermUpdate
from app.middlewares.exception_handler import BusinessException


class TermService:
    """术语服务类"""

    @staticmethod
    async def create(db, data: TermCreate) -> Term:
        """创建术语"""
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
        logger.info(f"创建术语: {term.term} (ID: {term.id})")
        return term

    @staticmethod
    async def get_by_id(db, term_id: int) -> Optional[Term]:
        """根据ID获取术语"""
        stmt = select(Term).where(Term.id == term_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db, code: str) -> Optional[Term]:
        """根据代码获取术语"""
        stmt = select(Term).where(Term.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[Term]:
        """获取所有术语"""
        stmt = select(Term).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search(db, keyword: str) -> List[Term]:
        """搜索术语"""
        stmt = select(Term).where(
            (Term.term.contains(keyword)) | (Term.code.contains(keyword))
        ).limit(50)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db, term_id: int, data: TermUpdate) -> Optional[Term]:
        """更新术语"""
        term = await TermService.get_by_id(db, term_id)
        if not term:
            raise BusinessException(code=404, message="术语不存在")

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
        logger.info(f"更新术语: {term.term} (ID: {term.id})")
        return term

    @staticmethod
    async def delete(db, term_id: int) -> None:
        """删除术语"""
        term = await TermService.get_by_id(db, term_id)
        if not term:
            raise BusinessException(code=404, message="术语不存在")

        await db.delete(term)
        await db.commit()
        logger.info(f"删除术语: {term.term} (ID: {term_id})")


term_service = TermService()
