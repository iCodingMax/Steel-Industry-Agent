"""
工具配置 API 路由
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from loguru import logger
import json

from app.core.database import get_db_session
from app.middlewares.auth_deps import get_current_user
from app.models.user import User
from app.schemas.tool import (
    MCPCreate, MCPUpdate, SkillCreate, SkillUpdate,
    MCPTestRequest
)
from app.services.tool_config_service import tool_config_service
from app.middlewares.exception_handler import BusinessException, success_response, error_response

router = APIRouter(prefix="/tools", tags=["工具管理"])


@router.get("")
async def list_tools(
    tool_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """获取工具列表"""
    try:
        tools = await tool_config_service.get_all(db, tool_type)
        return success_response(data=[t.to_dict() for t in tools])
    except Exception as e:
        logger.error(f"获取工具列表失败: {e}")
        return error_response(message=str(e))


@router.get("/{tool_id}")
async def get_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """获取单个工具详情"""
    try:
        tool = await tool_config_service.get_by_id(db, tool_id)
        if not tool:
            return error_response(message="工具不存在", code=404)
        return success_response(data=tool.to_dict())
    except Exception as e:
        logger.error(f"获取工具详情失败: {e}")
        return error_response(message=str(e))


@router.post("/mcp")
async def create_mcp(
    data: MCPCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """创建 MCP 配置"""
    try:
        tool = await tool_config_service.create_mcp(db, data, user.id)
        return success_response(data=tool.to_dict(), message="MCP创建成功")
    except Exception as e:
        logger.error(f"创建MCP失败: {e}")
        return error_response(message=str(e))


@router.put("/mcp/{tool_id}")
async def update_mcp(
    tool_id: int,
    data: MCPUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """更新 MCP 配置"""
    try:
        tool = await tool_config_service.update_mcp(db, tool_id, data)
        return success_response(data=tool.to_dict(), message="MCP更新成功")
    except Exception as e:
        logger.error(f"更新MCP失败: {e}")
        return error_response(message=str(e))


@router.post("/mcp/test")
async def test_mcp_connection(
    data: MCPTestRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """测试 MCP 连接 (MaxKB 格式)"""
    try:
        from app.services.mcp_client_service import mcp_client_service
        
        mcp_config = data.mcp_config
        
        # 解析 MaxKB 格式配置: {"服务名": {"url": "...", "transport": "sse"}}
        # 注意：Pydantic解析后 service_config 是 MCPConfig 对象，不是 dict
        url = None
        transport = "sse"
        service_name = None
        
        if mcp_config and len(mcp_config) == 1:
            service_name, service_config = list(mcp_config.items())[0]
            # 兼容 MCPConfig 对象和 dict 两种情况
            if hasattr(service_config, 'url'):
                url = service_config.url
                transport = service_config.transport
            elif isinstance(service_config, dict):
                url = service_config.get("url", "")
                transport = service_config.get("transport", "sse")
        
        if not url:
            return error_response(message="MCP配置缺少URL")
        
        # 清洗URL（去除可能残留的空格和反引号）
        url = url.strip().strip('`').strip()
        transport = (transport or "sse").strip()
        
        # 检查URL格式
        if not url.startswith(("http://", "https://")):
            return error_response(message=f"URL格式错误，必须以http://或https://开头")
        
        # 真实测试MCP连接：先初始化会话，再获取工具列表
        import time
        start_time = time.time()
        
        try:
            # 第一步：初始化MCP会话（验证SSE连接和协议握手）
            init_success = await mcp_client_service._initialize_mcp_session(url, transport)

            elapsed_time = round(time.time() - start_time, 2)

            if not init_success:
                # 初始化失败 = 连接不可用
                return success_response(data={
                    "reachable": False,
                    "serviceName": service_name,
                    "url": url,
                    "transport": transport,
                    "toolCount": 0,
                    "sampleTools": [],
                    "responseTime": f"{elapsed_time}s",
                    "message": f"连接失败：无法建立MCP会话（SSE连接超时或协议握手失败）"
                }, message="MCP连接测试失败：无法建立会话")

            # 第二步：获取工具列表（初始化成功后）
            test_tools = await mcp_client_service._fetch_mcp_tools(
                url=url,
                transport=transport,
                service_name=service_name or "test_service",
                server_name="connection_test"
            )

            elapsed_time = round(time.time() - start_time, 2)

            # 过滤掉默认fallback工具（以 _tool 或 _default 结尾的自动生成工具名）
            real_tools = [
                t for t in test_tools
                if not t.get('tool_name', '').endswith('_tool') and not t.get('tool_name', '').endswith('_default')
            ]

            if real_tools:
                tool_count = len(real_tools)
                tool_names = [t.get('tool_name', '') for t in real_tools[:5]]

                return success_response(data={
                    "reachable": True,
                    "serviceName": service_name,
                    "url": url,
                    "transport": transport,
                    "toolCount": tool_count,
                    "sampleTools": tool_names,
                    "responseTime": f"{elapsed_time}s",
                    "message": f"连接成功，发现 {tool_count} 个可用工具"
                }, message=f"MCP连接测试成功，发现 {tool_count} 个工具")
            else:
                return success_response(data={
                    "reachable": True,
                    "serviceName": service_name,
                    "url": url,
                    "transport": transport,
                    "toolCount": 0,
                    "sampleTools": [],
                    "responseTime": f"{elapsed_time}s",
                    "message": "连接成功，但未发现工具（可能需要配置权限）"
                }, message="MCP连接测试成功，但未发现工具")

        except Exception as e:
            elapsed_time = round(time.time() - start_time, 2)
            logger.warning(f"MCP连接测试异常: {url}, 错误={e}")

            return success_response(data={
                "reachable": False,
                "serviceName": service_name,
                "url": url,
                "transport": transport,
                "toolCount": 0,
                "sampleTools": [],
                "responseTime": f"{elapsed_time}s",
                "message": f"连接失败: {str(e)}"
            }, message=f"MCP连接测试失败: {str(e)}")
            
    except Exception as e:
        logger.error(f"MCP连接测试失败: {e}")
        return error_response(message=f"MCP连接测试失败: {str(e)}")


@router.post("/skill")
async def create_skill(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """创建 Skill (带文件上传)"""
    try:
        # 读取文件内容
        file_content = await file.read()
        file_name = file.filename or "skill.zip"

        from app.schemas.tool import SkillCreate
        skill_data = SkillCreate(
            name=name,
            description=description
        )

        tool = await tool_config_service.create_skill(
            db, skill_data, file_content, file_name, user.id
        )
        return success_response(data=tool.to_dict(), message="Skill创建成功")
    except Exception as e:
        logger.error(f"创建Skill失败: {e}")
        return error_response(message=str(e))


@router.put("/skill/{tool_id}")
async def update_skill(
    tool_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    remove_file: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """更新 Skill (可选替换文件或删除文件)"""
    try:
        from app.schemas.tool import SkillUpdate
        skill_data = SkillUpdate(
            name=name,
            description=description,
            status=status
        )

        file_content = None
        file_name = None
        if file:
            file_content = await file.read()
            file_name = file.filename

        # 判断是否需要删除文件
        need_remove_file = remove_file == 'true'

        tool = await tool_config_service.update_skill(
            db, tool_id, skill_data, file_content, file_name, need_remove_file
        )
        return success_response(data=tool.to_dict(), message="Skill更新成功")
    except Exception as e:
        logger.error(f"更新Skill失败: {e}")
        return error_response(message=str(e))


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """删除工具"""
    try:
        await tool_config_service.delete(db, tool_id)
        return success_response(message="删除成功")
    except Exception as e:
        logger.error(f"删除工具失败: {e}")
        return error_response(message=str(e))


@router.put("/{tool_id}/status")
async def update_tool_status(
    tool_id: int,
    status: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user)
):
    """更新工具状态"""
    try:
        tool = await tool_config_service.update_status(db, tool_id, status)
        return success_response(data=tool.to_dict(), message="状态更新成功")
    except Exception as e:
        logger.error(f"更新工具状态失败: {e}")
        return error_response(message=str(e))
