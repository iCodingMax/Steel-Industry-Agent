"""
工具配置服务
"""
from typing import List, Optional
from sqlalchemy import select
from loguru import logger
import os
import json
import zipfile
import shutil
from datetime import datetime

from app.models.tool_config import ToolConfig
from app.schemas.tool import MCPCreate, MCPUpdate, SkillCreate, SkillUpdate
from app.middlewares.exception_handler import BusinessException


# 项目根目录（backend/），基于当前文件位置计算
# tool_config_service.py 位于 backend/app/services/，向上3层即为 backend/
from pathlib import Path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

# Skill 文件存储目录（相对项目根目录）
SKILL_RELATIVE_DIR = os.path.join('uploads', 'skills')


def resolve_skill_path(relative_path: str) -> str:
    """
    将数据库中存储的相对路径解析为绝对路径

    :param relative_path: 数据库中存储的相对路径（如 "uploads/skills/skill_xxx.zip"）
    :return: 绝对路径
    """
    if not relative_path:
        return ''
    # 如果已经是绝对路径，直接返回（兼容旧数据）
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(_PROJECT_ROOT, relative_path)


def to_relative_path(absolute_path: str) -> str:
    """
    将绝对路径转为相对路径，用于存储到数据库

    :param absolute_path: 绝对路径
    :return: 相对路径（相对于项目根目录）
    """
    if not absolute_path:
        return ''
    # 尝试转为相对项目根目录的路径
    try:
        rel = os.path.relpath(absolute_path, _PROJECT_ROOT)
        # 如果结果不以 .. 开头，说明在项目根目录内
        if not rel.startswith('..'):
            return rel.replace('\\', '/')
    except ValueError:
        pass
    # 回退：如果已经是相对路径，直接返回
    return absolute_path.replace('\\', '/')


class ToolConfigService:
    """工具配置服务类"""

    @staticmethod
    async def get_all(db, tool_type: Optional[str] = None) -> List[ToolConfig]:
        """获取所有工具配置"""
        query = select(ToolConfig)
        if tool_type:
            query = query.where(ToolConfig.tool_type == tool_type)
        result = await db.execute(query.order_by(ToolConfig.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db, tool_id: int) -> Optional[ToolConfig]:
        """根据ID获取工具"""
        result = await db.execute(
            select(ToolConfig).where(ToolConfig.id == tool_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_mcp(db, data: MCPCreate, user_id: int = None) -> ToolConfig:
        """创建 MCP 配置 (MaxKB 格式)"""
        # mcp_config 已经通过 Schema 验证
        # 注意：Pydantic解析后 service_config 是 MCPConfig 对象，需要转为 dict 存储
        mcp_config = data.mcp_config

        # 验证基本结构
        if not isinstance(mcp_config, dict) or len(mcp_config) != 1:
            raise BusinessException(message="MCP配置必须包含一个服务配置")

        # 将 MCPConfig 对象转为普通 dict 存储
        plain_config = {}
        for service_name, service_config in mcp_config.items():
            if hasattr(service_config, 'model_dump'):
                # MCPConfig Pydantic 对象
                plain_config[service_name] = service_config.model_dump()
            elif isinstance(service_config, dict):
                plain_config[service_name] = service_config
            else:
                raise BusinessException(message=f"服务配置格式错误: {service_name}")

            # 再次验证URL存在
            url = plain_config[service_name].get('url', '')
            if not url:
                raise BusinessException(message=f"服务 {service_name} 必须包含 url 字段")

        tool = ToolConfig(
            name=data.name,
            description=data.description,
            tool_type="mcp",
            status="active",
            mcp_config=plain_config,
            timeout=30,
            created_by=user_id
        )
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        logger.info(f"创建MCP配置成功: {tool.name} (ID: {tool.id})")
        return tool

    @staticmethod
    async def update_mcp(db, tool_id: int, data: MCPUpdate) -> ToolConfig:
        """更新 MCP 配置"""
        tool = await ToolConfigService.get_by_id(db, tool_id)
        if not tool:
            raise BusinessException(message="工具不存在")
        if tool.tool_type != "mcp":
            raise BusinessException(message="非MCP类型工具")

        update_data = data.model_dump(exclude_unset=True)

        # 如果更新了 mcp_config，需要将 MCPConfig 对象转为 dict
        if 'mcp_config' in update_data and update_data['mcp_config']:
            plain_config = {}
            for service_name, service_config in update_data['mcp_config'].items():
                if hasattr(service_config, 'model_dump'):
                    plain_config[service_name] = service_config.model_dump()
                elif isinstance(service_config, dict):
                    plain_config[service_name] = service_config
            update_data['mcp_config'] = plain_config

        for key, value in update_data.items():
            setattr(tool, key, value)

        await db.commit()
        await db.refresh(tool)
        logger.info(f"更新MCP配置成功: {tool.name} (ID: {tool.id})")
        return tool

    @staticmethod
    async def delete(db, tool_id: int) -> None:
        """删除工具"""
        tool = await ToolConfigService.get_by_id(db, tool_id)
        if not tool:
            raise BusinessException(message="工具不存在")

        # 如果是 Skill，删除关联的文件
        if tool.tool_type == "skill" and tool.skill_file_path:
            try:
                abs_path = resolve_skill_path(tool.skill_file_path)
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    logger.debug(f"删除Skill文件: {abs_path}")
            except Exception as e:
                logger.warning(f"删除Skill文件失败: {e}")

        await db.delete(tool)
        await db.commit()
        logger.info(f"删除工具成功: {tool.name} (ID: {tool.id})")

    @staticmethod
    async def create_skill(
        db,
        data: SkillCreate,
        file_content: bytes,
        file_name: str,
        user_id: int = None
    ) -> ToolConfig:
        """创建 Skill (带文件上传)"""
        # 验证文件
        if not file_name.endswith('.zip'):
            raise BusinessException(message="Skill文件必须是ZIP格式")
        
        if len(file_content) > 100 * 1024 * 1024:  # 100MB
            raise BusinessException(message="Skill文件大小不能超过100MB")

        # 创建存储目录（使用项目根目录下的相对路径）
        upload_dir = os.path.join(_PROJECT_ROOT, SKILL_RELATIVE_DIR)
        os.makedirs(upload_dir, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_name = f"skill_{timestamp}_{file_name}"
        abs_path = os.path.join(upload_dir, unique_name)
        relative_path = to_relative_path(abs_path)

        # 保存文件
        with open(abs_path, 'wb') as f:
            f.write(file_content)

        # 验证ZIP文件有效性
        try:
            with zipfile.ZipFile(abs_path, 'r') as zf:
                # 检查是否包含必要的文件
                file_list = zf.namelist()
                logger.debug(f"Skill ZIP文件内容: {file_list}")
        except zipfile.BadZipFile:
            os.remove(abs_path)
            raise BusinessException(message="无效的ZIP文件")

        tool = ToolConfig(
            name=data.name,
            description=data.description,
            tool_type="skill",
            status="active",
            skill_file_path=relative_path,
            skill_file_name=file_name,
            timeout=30,
            created_by=user_id
        )
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        logger.info(f"创建Skill成功: {tool.name} (ID: {tool.id}), 存储路径: {relative_path}")
        return tool

    @staticmethod
    async def update_skill(
        db,
        tool_id: int,
        data: SkillUpdate,
        file_content: Optional[bytes] = None,
        file_name: Optional[str] = None,
        need_remove_file: bool = False
    ) -> ToolConfig:
        """更新 Skill 配置（可选替换文件或删除文件）"""
        tool = await ToolConfigService.get_by_id(db, tool_id)
        if not tool:
            raise BusinessException(message="工具不存在")
        if tool.tool_type != "skill":
            raise BusinessException(message="非Skill类型工具")

        # 更新基础字段
        if data.name is not None:
            tool.name = data.name
        if data.description is not None:
            tool.description = data.description
        if data.status is not None:
            tool.status = data.status

        # 如果需要删除文件
        if need_remove_file and not file_content:
            if tool.skill_file_path:
                abs_path = resolve_skill_path(tool.skill_file_path)
                if abs_path and os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                        logger.debug(f"删除Skill文件: {abs_path}")
                    except Exception as e:
                        logger.warning(f"删除Skill文件失败: {e}")
            tool.skill_file_path = None
            tool.skill_file_name = None

        # 如果提供了新文件，替换原文件
        if file_content and file_name:
            # 验证文件
            if not file_name.endswith('.zip'):
                raise BusinessException(message="Skill文件必须是ZIP格式")
            if len(file_content) > 100 * 1024 * 1024:
                raise BusinessException(message="Skill文件大小不能超过100MB")

            # 删除旧文件
            if tool.skill_file_path:
                old_abs_path = resolve_skill_path(tool.skill_file_path)
                if old_abs_path and os.path.exists(old_abs_path):
                    try:
                        os.remove(old_abs_path)
                    except Exception as e:
                        logger.warning(f"删除旧Skill文件失败: {e}")

            # 保存新文件
            upload_dir = os.path.join(_PROJECT_ROOT, SKILL_RELATIVE_DIR)
            os.makedirs(upload_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_name = f"skill_{timestamp}_{file_name}"
            abs_path = os.path.join(upload_dir, unique_name)

            with open(abs_path, 'wb') as f:
                f.write(file_content)

            # 验证ZIP文件有效性
            try:
                with zipfile.ZipFile(abs_path, 'r') as zf:
                    pass
            except zipfile.BadZipFile:
                os.remove(abs_path)
                raise BusinessException(message="无效的ZIP文件")

            tool.skill_file_path = to_relative_path(abs_path)
            tool.skill_file_name = file_name

        await db.commit()
        await db.refresh(tool)
        logger.info(f"更新Skill成功: {tool.name} (ID: {tool.id})")
        return tool

    @staticmethod
    async def delete_skill_file(db, tool_id: int) -> None:
        """删除 Skill 文件 (保留配置)"""
        tool = await ToolConfigService.get_by_id(db, tool_id)
        if not tool or tool.tool_type != "skill":
            raise BusinessException(message="Skill不存在")

        if tool.skill_file_path:
            abs_path = resolve_skill_path(tool.skill_file_path)
            if abs_path and os.path.exists(abs_path):
                os.remove(abs_path)
            tool.skill_file_path = None
            tool.skill_file_name = None
            await db.commit()
            logger.info(f"删除Skill文件: {tool.name}")

    @staticmethod
    async def update_status(db, tool_id: int, status: str) -> ToolConfig:
        """更新工具状态"""
        tool = await ToolConfigService.get_by_id(db, tool_id)
        if not tool:
            raise BusinessException(message="工具不存在")
        
        tool.status = status
        await db.commit()
        await db.refresh(tool)
        return tool


# 服务实例
tool_config_service = ToolConfigService()
logger.info("工具配置服务实例已创建")
