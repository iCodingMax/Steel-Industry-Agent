"""
大模型配置相关Schema
"""
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class LLMConfigCreate(BaseModel):
    """创建LLM配置请求"""
    name: str = Field(..., description="配置名称")
    type: str = Field(..., description="类型: xinference/newapi/openai")
    baseUrl: str = Field(..., description="服务地址")
    apiKey: Optional[str] = Field(None, description="API密钥")
    modelName: str = Field(..., description="模型名称")
    modelType: Optional[str] = Field(None, description="模型类型: embedding/rerank/llm")
    maxTokens: int = Field(default=2048, description="最大输出token")
    temperature: float = Field(default=0.7, description="温度参数")
    topP: Optional[float] = Field(None, description="Top-p采样")
    extraParams: Optional[Dict] = Field(default_factory=dict, description="额外参数")
    isDefault: bool = Field(default=False, description="是否默认配置")
    description: Optional[str] = Field(None, description="描述")


class LLMConfigUpdate(BaseModel):
    """更新LLM配置请求"""
    name: Optional[str] = Field(None, description="配置名称")
    type: Optional[str] = Field(None, description="类型")
    baseUrl: Optional[str] = Field(None, description="服务地址")
    apiKey: Optional[str] = Field(None, description="API密钥")
    modelName: Optional[str] = Field(None, description="模型名称")
    modelType: Optional[str] = Field(None, description="模型类型")
    maxTokens: Optional[int] = Field(None, description="最大输出token")
    temperature: Optional[float] = Field(None, description="温度参数")
    topP: Optional[float] = Field(None, description="Top-p采样")
    extraParams: Optional[Dict] = Field(None, description="额外参数")
    isDefault: Optional[bool] = Field(None, description="是否默认配置")
    status: Optional[str] = Field(None, description="状态")
    description: Optional[str] = Field(None, description="描述")


class LLMConfigResponse(BaseModel):
    """LLM配置响应"""
    id: int
    name: str
    type: str
    baseUrl: str
    apiKey: Optional[str]
    modelName: str
    modelType: Optional[str]
    maxTokens: int
    temperature: float
    topP: Optional[float]
    extraParams: Dict
    isDefault: bool
    status: str
    description: Optional[str]
    createdAt: Optional[str]
    updatedAt: Optional[str]
