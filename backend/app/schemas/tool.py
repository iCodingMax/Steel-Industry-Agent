"""
工具配置 Schema
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any


class ToolConfigBase(BaseModel):
    """工具配置基础模型"""
    name: str = Field(description="工具名称", max_length=100)
    description: Optional[str] = Field(None, description="工具描述")
    tool_type: str = Field(description="工具类型: mcp/skill")
    status: Optional[str] = Field("active", description="状态: active/inactive")
    timeout: Optional[int] = Field(30, description="执行超时时间(秒)")


class MCPConfig(BaseModel):
    """MCP Server 配置 (兼容 Claude Code / MaxKB 格式)
    
    格式示例 (Claude Code 风格):
    {
        "mcp_server_mysql": {
            "url": "http://127.0.0.1:8010/mcp",
            "type": "http",
            "headers": {"Authorization": "Bearer blast_furnace"}
        }
    }
    
    格式示例 (MaxKB 风格):
    {
        "amap-amap-sse": {
            "url": "http://mcp.amap.com/sse?key=xxx",
            "transport": "sse"
        }
    }
    """
    model_config = {"extra": "allow"}  # 允许额外字段（如 headers, bearer_token, type）
    
    url: str = Field(description="MCP Server URL")
    transport: Optional[str] = Field(default=None, description="传输协议: sse/streamable-http（可省略，type会自动映射）")
    type: Optional[str] = Field(default=None, description="Claude Code 风格: http → streamable-http, sse → sse")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP 请求头（含 Authorization 认证）")
    bearer_token: Optional[str] = Field(default=None, description="简化认证：自动构造 Authorization: Bearer xxx")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """清洗URL：去除首尾空格、反引号等非法字符"""
        if not v:
            raise ValueError("URL不能为空")
        v = v.strip().strip('`').strip('"').strip("'").strip()
        if not v:
            raise ValueError("URL不能为空")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL必须以http://或https://开头，当前值: {v}")
        return v

    @model_validator(mode='after')
    def normalize_transport_and_type(self) -> 'MCPConfig':
        """
        统一 transport/type 别名，自动归一化
        
        映射规则:
          - type="http" / transport="http" → "streamable-http"
          - type="sse" / transport="sse" → "sse"
          - 默认 → "streamable-http"（优先现代协议）
        """
        # 优先用 transport，其次 type
        raw = self.transport or self.type
        raw = (raw or '').lower().strip()
        
        if raw in ('sse', 'eventsource', 'event-source'):
            self.transport = 'sse'
        else:
            # http / streamable-http / 其他未知值 → 统一为 streamable-http
            self.transport = 'streamable-http'
        
        # 同步 type 字段为归一化后的值
        self.type = self.transport
        return self


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
