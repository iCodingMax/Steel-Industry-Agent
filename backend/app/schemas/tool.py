"""
工具配置 Schema
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any


class ToolConfigBase(BaseModel):
    """工具配置基础模型"""
    name: str = Field(description="工具名称", max_length=100)
    description: Optional[str] = Field(None, description="工具描述")
    tool_type: str = Field(description="工具类型: mcp/skill")
    status: Optional[str] = Field("active", description="状态: active/inactive")
    timeout: Optional[int] = Field(30, description="执行超时时间(秒)")


class MCPConfig(BaseModel):
    """MCP Server 配置 (MaxKB 格式)
    
    格式示例:
    {
        "amap-amap-sse": {
            "url": "http://mcp.amap.com/sse?key=xxx",
            "transport": "sse"
        }
    }
    """
    url: str = Field(description="MCP Server URL")
    transport: str = Field(default="sse", description="传输协议: sse/streamable-http")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """清洗URL：去除首尾空格、反引号等非法字符"""
        if not v:
            raise ValueError("URL不能为空")
        # 去除首尾空格、反引号、引号等常见复制粘贴引入的非法字符
        v = v.strip().strip('`').strip('"').strip("'").strip()
        if not v:
            raise ValueError("URL不能为空")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL必须以http://或https://开头，当前值: {v}")
        return v

    @field_validator('transport')
    @classmethod
    def validate_transport(cls, v: str) -> str:
        if v not in ['sse', 'streamable-http']:
            raise ValueError(f"不支持的传输协议: {v}，仅支持 sse 和 streamable-http")
        return v


class MCPCreate(BaseModel):
    """MCP创建请求"""
    name: str = Field(description="MCP名称", max_length=100)
    description: Optional[str] = Field(None, description="描述")
    mcp_config: Dict[str, MCPConfig] = Field(description="MCP Server配置 (MaxKB格式: {服务名: {url, transport}})")
    
    @field_validator('mcp_config')
    @classmethod
    def validate_mcp_config(cls, v: Dict[str, MCPConfig]) -> Dict[str, MCPConfig]:
        if not v:
            raise ValueError("MCP配置不能为空")
        if len(v) != 1:
            raise ValueError("MCP配置必须包含且仅包含一个服务配置")
        return v


class MCPUpdate(BaseModel):
    """MCP更新请求"""
    name: Optional[str] = Field(None, description="MCP名称", max_length=100)
    description: Optional[str] = Field(None, description="描述")
    mcp_config: Optional[Dict[str, MCPConfig]] = Field(None, description="MCP Server配置 (MaxKB格式)")
    status: Optional[str] = Field(None, description="状态")


class SkillCreate(BaseModel):
    """Skill创建请求"""
    name: str = Field(description="Skill名称", max_length=100)
    description: Optional[str] = Field(None, description="描述")


class SkillUpdate(BaseModel):
    """Skill更新请求"""
    name: Optional[str] = Field(None, description="Skill名称", max_length=100)
    description: Optional[str] = Field(None, description="描述")
    status: Optional[str] = Field(None, description="状态")


class ToolConfigResponse(BaseModel):
    """工具配置响应"""
    id: int
    name: str
    description: Optional[str]
    tool_type: str
    status: str
    mcp_config: Optional[Dict[str, Any]]
    skill_file_path: Optional[str]
    skill_file_name: Optional[str]
    timeout: int
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class MCPTestRequest(BaseModel):
    """MCP测试连接请求"""
    mcp_config: Dict[str, MCPConfig] = Field(description="MCP Server配置 (MaxKB格式)")
