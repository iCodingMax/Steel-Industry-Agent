"""
MCP 客户端服务

本模块负责 MCP (Model Context Protocol) 工具的加载和调用。
支持 SSE 和 Streamable HTTP 两种传输协议。

核心功能：
1. 加载应用关联的 MCP 配置
2. 解析 MaxKB 格式的 MCP Server 配置
3. 调用 MCP 工具并返回结果
4. 支持多 MCP 服务并行调用

配置格式 (MaxKB):
{
    "服务名": {
        "url": "http://mcp-server/sse?key=xxx",
        "transport": "sse"
    }
}

MCP SSE 协议流程：
1. 客户端 GET 请求 SSE 端点，建立 SSE 长连接
2. 服务器通过 SSE 返回 endpoint URL（含 session_id）
3. 客户端 POST 到 endpoint URL 发送 JSON-RPC 请求（initialize → tools/list → tools/call）
4. 服务器通过 SSE 长连接返回 JSON-RPC 响应
"""
import json
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_config import ToolConfig


class MCPClientService:
    """
    MCP 客户端服务
    
    负责管理 MCP Server 的连接和工具调用。
    支持 MaxKB 格式的配置：{"服务名": {"url": "...", "transport": "sse"}}
    
    MCP SSE 协议通信流程：
    1. GET 请求 SSE URL，建立长连接，获取 endpoint URL（含 session_id）
    2. POST 到 endpoint URL 发送 JSON-RPC 请求
    3. 响应通过 SSE 长连接返回
    """

    # JSON-RPC 请求ID计数器
    _request_id = 0

    @classmethod
    def _get_next_id(cls) -> int:
        """获取下一个请求ID"""
        cls._request_id += 1
        return cls._request_id

    @staticmethod
    def _build_base_url(url: str, path: str) -> str:
        """
        将相对路径拼接为完整URL

        :param url: 原始SSE URL
        :param path: 相对路径（如 /messages?session_id=xxx）
        :return: 完整URL
        """
        if path.startswith("http://") or path.startswith("https://"):
            return path
        parsed = httpx.URL(url)
        base = f"{parsed.scheme}://{parsed.host}"
        if parsed.port:
            base += f":{parsed.port}"
        return base + path

    @staticmethod
    async def _mcp_sse_session(
        url: str,
        payload: Dict[str, Any],
        timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """
        通过 MCP SSE 协议发送 JSON-RPC 请求并获取响应

        完整流程：
        1. GET 请求 SSE URL，建立长连接
        2. 从 SSE 流中读取 endpoint URL（含 session_id）
        3. POST 到 endpoint URL 发送 JSON-RPC 请求
        4. 从 SSE 流中读取 JSON-RPC 响应

        :param url: MCP Server SSE URL
        :param payload: JSON-RPC 请求体
        :param timeout: 总超时时间
        :return: JSON-RPC 响应数据或 None
        """
        client = None
        sse_task = None
        try:
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                follow_redirects=True
            )

            # 使用队列接收 SSE 事件
            response_queue: asyncio.Queue = asyncio.Queue()
            endpoint_ready = asyncio.Event()
            endpoint_url_holder: Dict[str, Optional[str]] = {"value": None}
            sse_closed = asyncio.Event()

            async def _read_sse_stream():
                """后台读取 SSE 流，提取 endpoint URL 和 JSON-RPC 响应"""
                try:
                    async with client.stream(
                        "GET", url,
                        headers={"Accept": "text/event-stream"}
                    ) as response:
                        if response.status_code != 200:
                            logger.warning(f"MCP SSE连接失败: status={response.status_code}, url={url}")
                            await response_queue.put(None)
                            return

                        current_event = ""
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line:
                                current_event = ""
                                continue

                            # 解析 SSE event 字段
                            if line.startswith("event:"):
                                current_event = line[6:].strip()
                                continue

                            # 解析 SSE data 字段
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    continue

                                # 1. 提取 endpoint URL（第一条消息）
                                if not endpoint_url_holder["value"]:
                                    # endpoint 可能是纯URL路径或JSON
                                    if data_str.startswith("http") or data_str.startswith("/"):
                                        endpoint_url = MCPClientService._build_base_url(url, data_str)
                                        endpoint_url_holder["value"] = endpoint_url
                                        endpoint_ready.set()
                                        logger.debug(f"MCP endpoint URL: {endpoint_url}")
                                        continue
                                    else:
                                        try:
                                            data_json = json.loads(data_str)
                                            # 尝试从 JSON 中提取 endpoint
                                            ep = data_json.get("endpoint") or data_json.get("uri")
                                            if ep:
                                                endpoint_url = MCPClientService._build_base_url(url, ep)
                                                endpoint_url_holder["value"] = endpoint_url
                                                endpoint_ready.set()
                                                logger.debug(f"MCP endpoint URL: {endpoint_url}")
                                                continue
                                        except json.JSONDecodeError:
                                            pass

                                # 2. 解析 JSON-RPC 响应
                                try:
                                    rpc_response = json.loads(data_str)
                                    # 确保是 JSON-RPC 响应（有 jsonrpc 字段或 result/error 字段）
                                    if isinstance(rpc_response, dict) and (
                                        "jsonrpc" in rpc_response or
                                        "result" in rpc_response or
                                        "error" in rpc_response
                                    ):
                                        await response_queue.put(rpc_response)
                                except json.JSONDecodeError:
                                    logger.debug(f"无法解析SSE数据: {data_str[:100]}")

                except httpx.ConnectError as e:
                    logger.debug(f"MCP SSE连接失败: {url}, 错误={e}")
                    await response_queue.put(None)
                except httpx.TimeoutException:
                    logger.debug(f"MCP SSE连接超时: {url}")
                    await response_queue.put(None)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"MCP SSE读取异常: {url}, 错误={e}")
                    await response_queue.put(None)
                finally:
                    sse_closed.set()

            # 启动后台 SSE 读取任务
            sse_task = asyncio.create_task(_read_sse_stream())

            # 等待 endpoint URL（最多10秒）
            try:
                await asyncio.wait_for(endpoint_ready.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"等待MCP endpoint超时: {url}")
                return None

            endpoint_url = endpoint_url_holder["value"]
            if not endpoint_url:
                logger.warning(f"未获取到MCP endpoint URL: {url}")
                return None

            # POST 到 endpoint URL 发送 JSON-RPC 请求
            try:
                post_response = await client.post(
                    endpoint_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    }
                )

                # 某些 MCP Server 直接通过 POST 返回 JSON 响应
                if post_response.status_code == 200:
                    content_type = post_response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        try:
                            return post_response.json()
                        except Exception:
                            pass
                    elif "text/event-stream" in content_type:
                        parsed = MCPClientService._parse_sse_event(post_response.text)
                        if parsed:
                            return parsed
                elif post_response.status_code == 202:
                    # 202 Accepted: 响应将通过 SSE 流返回
                    pass
                else:
                    logger.warning(f"MCP POST请求失败: status={post_response.status_code}, url={endpoint_url}")
            except Exception as e:
                logger.debug(f"MCP POST请求异常: {endpoint_url}, 错误={e}")

            # 从 SSE 流读取响应（POST后响应通过SSE返回）
            try:
                result = await asyncio.wait_for(response_queue.get(), timeout=20.0)
                return result
            except asyncio.TimeoutError:
                logger.warning(f"等待MCP SSE响应超时: {url}")
                return None

        except Exception as e:
            logger.error(f"MCP SSE会话异常: {url}, 错误={e}")
            return None
        finally:
            if sse_task and not sse_task.done():
                sse_task.cancel()
                try:
                    await asyncio.wait_for(sse_task, timeout=3.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            if client:
                await client.aclose()

    @staticmethod
    async def load_mcp_tools(
        db: AsyncSession,
        tool_config_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        加载指定 MCP 配置的工具列表
        
        :param db: 数据库会话
        :param tool_config_ids: MCP 配置ID列表
        :return: MCP工具列表，每个工具包含 name, description, parameters 等
        """
        tools = []
        
        for config_id in tool_config_ids:
            stmt = select(ToolConfig).where(
                (ToolConfig.id == config_id) &
                (ToolConfig.tool_type == 'mcp') &
                (ToolConfig.status == 'active')
            )
            result = await db.execute(stmt)
            config = result.scalar_one_or_none()
            
            if not config:
                logger.warning(f"MCP配置不存在或已禁用: ID={config_id}")
                continue
            
            # 解析 MCP 配置 (MaxKB 格式)
            mcp_config = config.mcp_config
            if not mcp_config:
                logger.warning(f"MCP配置为空: ID={config_id}")
                continue

            # 兼容 dict 和 Pydantic 对象
            if hasattr(mcp_config, 'model_dump'):
                mcp_config = mcp_config.model_dump()
            if not isinstance(mcp_config, dict):
                logger.warning(f"MCP配置格式错误: ID={config_id}")
                continue
            
            # 获取服务名和连接信息
            for service_name, service_config in mcp_config.items():
                # 兼容 MCPConfig 对象和 dict
                if hasattr(service_config, 'model_dump'):
                    service_config = service_config.model_dump()
                if not isinstance(service_config, dict):
                    continue
                
                url = service_config.get('url', '')
                transport = service_config.get('transport', 'sse')
                
                if not url:
                    continue

                # 清洗URL
                url = url.strip().strip('`').strip()
                
                # 尝试获取工具列表
                try:
                    service_tools = await MCPClientService._fetch_mcp_tools(
                        url, transport, service_name, config.name
                    )
                    tools.extend(service_tools)
                except Exception as e:
                    logger.warning(f"获取MCP工具列表失败: {service_name}, 错误={e}")
                    # 即使获取工具列表失败，也记录配置信息供后续使用
                    tools.append({
                        'server_id': config.id,
                        'server_name': config.name,
                        'service_name': service_name,
                        'tool_name': f"{service_name}_default",
                        'description': f"MCP服务: {config.name}",
                        'parameters': {
                            "type": "object",
                            "properties": {},
                            "description": f"通过MCP协议调用 {config.name} 的功能"
                        },
                        'url': url,
                        'transport': transport,
                    })
        
        return tools

    @staticmethod
    async def _fetch_mcp_tools(
        url: str,
        transport: str,
        service_name: str,
        server_name: str
    ) -> List[Dict[str, Any]]:
        """
        从 MCP Server 获取工具列表
        
        :param url: MCP Server URL
        :param transport: 传输协议 (sse/streamable-http)
        :param service_name: 服务名
        :param server_name: 服务器名
        :return: 工具列表
        """
        tools = []
        
        try:
            # 先初始化MCP会话
            init_success = await MCPClientService._initialize_mcp_session(url, transport)
            if not init_success:
                logger.warning(f"MCP会话初始化失败: {url}")
                # 仍然返回默认工具，允许后续尝试调用
                tools.append({
                    'server_id': None,
                    'server_name': server_name,
                    'service_name': service_name,
                    'tool_name': f"{service_name}_tool",
                    'description': f"来自 {server_name} 的MCP工具",
                    'parameters': {
                        "type": "object",
                        "properties": {},
                        "description": f"通过MCP协议调用 {server_name} 的功能"
                    },
                    'url': url,
                    'transport': transport,
                })
                return tools

            # 构建 JSON-RPC 请求：tools/list
            request_id = MCPClientService._get_next_id()
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {}
            }
            
            # 发送请求并解析响应
            response_data = await MCPClientService._send_jsonrpc_request(
                url=url,
                payload=payload,
                transport=transport,
                timeout=15.0
            )
            
            if response_data:
                # 解析工具列表
                tools = MCPClientService._parse_tools_list(
                    response_data, service_name, server_name, url, transport
                )
                
        except httpx.ConnectError as e:
            logger.debug(f"MCP Server连接失败: {url}, 错误={e}")
        except httpx.TimeoutException:
            logger.debug(f"MCP Server连接超时: {url}")
        except Exception as e:
            logger.debug(f"获取MCP工具列表异常: {url}, 错误={e}")
        
        # 如果无法获取工具列表，生成默认工具信息（允许后续调用尝试）
        if not tools:
            tools.append({
                'server_id': None,
                'server_name': server_name,
                'service_name': service_name,
                'tool_name': f"{service_name}_tool",
                'description': f"来自 {server_name} 的MCP工具",
                'parameters': {
                    "type": "object",
                    "properties": {},
                    "description": f"通过MCP协议调用 {server_name} 的功能"
                },
                'url': url,
                'transport': transport,
            })
        
        return tools

    @staticmethod
    async def _initialize_mcp_session(url: str, transport: str) -> bool:
        """
        初始化 MCP 会话（发送 initialize 请求和 initialized 通知）
        
        MCP 协议要求在 tools/list 或 tools/call 之前完成初始化握手
        
        :param url: MCP Server URL
        :param transport: 传输协议
        :return: 初始化是否成功
        """
        try:
            # 发送 initialize 请求
            request_id = MCPClientService._get_next_id()
            init_payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "steel-industry-agent",
                        "version": "1.0.0"
                    }
                }
            }

            init_response = await MCPClientService._send_jsonrpc_request(
                url=url,
                payload=init_payload,
                transport=transport,
                timeout=10.0
            )

            if not init_response:
                logger.debug(f"MCP initialize无响应: {url}")
                return False

            # 检查初始化是否成功
            if "error" in init_response:
                logger.warning(f"MCP initialize错误: {init_response['error']}")
                return False

            logger.debug(f"MCP initialize成功: {url}")

            # 发送 initialized 通知（不需要响应）
            notify_id = MCPClientService._get_next_id()
            notify_payload = {
                "jsonrpc": "2.0",
                "id": notify_id,
                "method": "notifications/initialized",
                "params": {}
            }

            # 通知不需要等待响应
            await MCPClientService._send_jsonrpc_request(
                url=url,
                payload=notify_payload,
                transport=transport,
                timeout=5.0
            )

            return True

        except Exception as e:
            logger.debug(f"MCP初始化异常: {url}, 错误={e}")
            return False

    @staticmethod
    async def _send_jsonrpc_request(
        url: str,
        payload: Dict[str, Any],
        transport: str = "sse",
        timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """
        发送 JSON-RPC 请求到 MCP Server
        
        根据 transport 类型选择通信方式：
        - sse: GET建立SSE连接 → POST发送请求 → SSE接收响应
        - streamable-http: 直接POST发送请求
        
        :param url: MCP Server URL
        :param payload: JSON-RPC 请求体
        :param transport: 传输协议
        :param timeout: 超时时间
        :return: 响应数据或None
        """
        if transport == "sse":
            return await MCPClientService._mcp_sse_session(url, payload, timeout)
        else:
            # Streamable HTTP: 直接POST
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                        }
                    )
                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "")
                        if "text/event-stream" in content_type:
                            return MCPClientService._parse_sse_event(response.text)
                        else:
                            return response.json()
                    else:
                        logger.warning(f"MCP Server返回错误: status={response.status_code}, url={url}")
                        return None
            except Exception as e:
                logger.error(f"MCP请求异常: {url}, 错误={e}")
                return None

    @staticmethod
    def _parse_sse_event(content: str) -> Optional[Dict[str, Any]]:
        """
        解析 SSE 响应内容
        
        SSE 格式:
        event: message
        data: {"jsonrpc": "2.0", "result": {...}, "id": 1}
        
        :param content: SSE 响应文本
        :return: 解析后的 JSON-RPC 数据
        """
        if not content:
            return None
            
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass
        
        # 解析 SSE 格式: data: {...}
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    continue
                try:
                    return json.loads(data_str)
                except json.JSONDecodeError:
                    continue
        
        # 尝试查找 JSON 对象
        try:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                json_str = content[start:end + 1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        return None

    @staticmethod
    def _parse_tools_list(
        response_data: Dict[str, Any],
        service_name: str,
        server_name: str,
        url: str,
        transport: str
    ) -> List[Dict[str, Any]]:
        """
        解析工具列表响应
        
        :param response_data: JSON-RPC 响应数据
        :param service_name: 服务名
        :param server_name: 服务器名
        :param url: MCP Server URL
        :param transport: 传输协议
        :return: 工具列表
        """
        tools = []
        
        if not response_data:
            return tools
        
        # 处理 JSON-RPC 响应格式
        result = response_data.get("result", response_data)
        
        # 检查是否包含 tools 列表
        if isinstance(result, dict) and "tools" in result:
            tools_list = result["tools"]
        elif isinstance(response_data, dict) and "tools" in response_data:
            tools_list = response_data["tools"]
        else:
            tools_list = []
        
        # 解析每个工具
        for tool in tools_list:
            if not isinstance(tool, dict):
                continue
            
            tool_name = tool.get('name', f"{service_name}_tool")
            description = tool.get('description', '')
            parameters = tool.get('inputSchema', tool.get('parameters', {}))
            
            tools.append({
                'server_id': None,
                'server_name': server_name,
                'service_name': service_name,
                'tool_name': tool_name,
                'description': description,
                'parameters': parameters,
                'url': url,
                'transport': transport,
            })
        
        return tools

    @staticmethod
    async def call_tool(
        tool_info: Dict[str, Any],
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用 MCP 工具
        
        :param tool_info: 工具信息（包含 url, transport, service_name, tool_name 等）
        :param arguments: 工具调用参数
        :return: 工具调用结果
        """
        url = tool_info.get('url', '')
        transport = tool_info.get('transport', 'sse')
        service_name = tool_info.get('service_name', '')
        tool_name = tool_info.get('tool_name', '')
        
        # 对于 MaxKB 格式，工具名可能包含服务名前缀
        actual_tool_name = tool_name
        if actual_tool_name.startswith(f"{service_name}_"):
            actual_tool_name = actual_tool_name[len(service_name) + 1:]
        
        try:
            # 先初始化MCP会话
            init_success = await MCPClientService._initialize_mcp_session(url, transport)
            if not init_success:
                logger.warning(f"MCP会话初始化失败，尝试直接调用: {url}")

            # 构建 JSON-RPC 请求：tools/call
            request_id = MCPClientService._get_next_id()
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": actual_tool_name,
                    "arguments": arguments
                }
            }
            
            # 发送请求
            response_data = await MCPClientService._send_jsonrpc_request(
                url=url,
                payload=payload,
                transport=transport,
                timeout=30.0
            )
            
            if response_data is None:
                return {
                    "success": False,
                    "result": "无法连接到MCP Server或请求超时"
                }
            
            # 解析工具调用结果
            return MCPClientService._parse_tool_call_result(response_data)
            
        except Exception as e:
            logger.error(f"工具调用异常: {tool_name}, 错误={e}")
            return {
                "success": False,
                "result": f"工具调用异常: {str(e)}"
            }

    @staticmethod
    def _parse_tool_call_result(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析工具调用结果
        
        :param response_data: JSON-RPC 响应数据
        :return: 标准化的结果
        """
        if not response_data:
            return {
                "success": False,
                "result": "空响应"
            }
        
        # 检查是否有错误
        if "error" in response_data:
            error = response_data["error"]
            return {
                "success": False,
                "result": f"工具调用错误: {error.get('message', str(error))}",
                "error": error
            }
        
        # 解析结果
        result = response_data.get("result", response_data)
        
        # 处理 MCP 标准结果格式
        if isinstance(result, dict):
            # result.content 可能是数组或字符串
            content = result.get("content", result)
            
            if isinstance(content, list):
                # content 是数组，每个元素包含 type 和 text
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))
                    elif isinstance(item, dict) and "text" in item:
                        texts.append(str(item.get("text", "")))
                return {
                    "success": True,
                    "result": "\n".join(texts) if texts else str(result),
                    "raw_result": result
                }
            elif isinstance(content, str):
                return {
                    "success": True,
                    "result": content,
                    "raw_result": result
                }
            else:
                return {
                    "success": True,
                    "result": str(content),
                    "raw_result": result
                }
        elif isinstance(result, str):
            return {
                "success": True,
                "result": result,
                "raw_result": result
            }
        else:
            return {
                "success": True,
                "result": str(result),
                "raw_result": result
            }

    @staticmethod
    async def execute_tool_calls(
        db: AsyncSession,
        tool_config_ids: List[int],
        question: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        执行工具调用流程
        
        1. 加载 MCP 工具列表
        2. 使用 LLM 分析用户问题，决定调用哪些工具
        3. 执行工具调用
        4. 使用 LLM 整合结果生成最终回答
        
        :param db: 数据库会话
        :param tool_config_ids: MCP 配置ID列表
        :param question: 用户问题
        :param system_prompt: 系统提示词
        :return: 工具调用结果，包含 answer, tool_calls, tool_results 等
        """
        from app.services.llm_service import llm_service
        
        result = {
            "answer": "",
            "tool_calls": [],
            "tool_results": [],
            "success": True
        }
        
        # 1. 加载 MCP 工具列表
        mcp_tools = await MCPClientService.load_mcp_tools(db, tool_config_ids)
        
        if not mcp_tools:
            result["answer"] = "抱歉，未找到可用的MCP工具。请先在应用设置中配置MCP服务。"
            result["success"] = False
            return result
        
        # 2. 构建工具描述供 LLM 使用
        tools_description = []
        for tool in mcp_tools:
            desc = {
                "name": tool['tool_name'],
                "description": tool.get('description', ''),
                "parameters": tool.get('parameters', {})
            }
            tools_description.append(desc)
        
        # 3. 使用 LLM 分析需要调用哪些工具
        tools_prompt = f"""你是一个工具调用助手。根据用户问题，判断应该使用哪些工具来回答问题。

可用工具列表：
{json.dumps(tools_description, ensure_ascii=False, indent=2)}

用户问题：{question}

请分析用户问题，返回应该调用的工具和参数。返回JSON格式：
{{
    "tool_calls": [
        {{
            "tool_name": "工具名",
            "arguments": {{
                "参数名": "参数值"
            }}
        }}
    ]
}}

如果不需要调用任何工具就能回答问题，返回：
{{
    "tool_calls": []
}}

注意：只返回JSON，不要返回其他内容。"""
        
        tool_decision_prompt = system_prompt + "\n\n" + tools_prompt if system_prompt else tools_prompt
        
        try:
            logger.info("开始分析工具调用决策...")
            
            # 调用 LLM 分析工具调用决策
            llm_response = await llm_service.chat(
                prompt=tool_decision_prompt,
                system_prompt=None,
                history=history,
            )
            
            logger.info(f"LLM工具决策返回: {llm_response[:200]}...")
            
            # 解析 LLM 返回的工具调用指令
            tool_decision = MCPClientService._parse_tool_decision(llm_response)
            
            if not tool_decision or not tool_decision.get("tool_calls"):
                # 不需要调用工具，直接回答
                logger.info("LLM判定不需要调用工具，直接回答用户问题")
                answer_prompt = f"""用户问题：{question}

请直接回答用户的问题。如果问题需要外部工具查询（如地图、天气、地理位置等），请告知用户当前系统没有可用的相关工具。"""
                
                result["answer"] = await llm_service.chat(
                    prompt=answer_prompt,
                    system_prompt=system_prompt,
                    history=history,
                )
                return result
            
            # 4. 执行工具调用
            logger.info(f"开始执行 {len(tool_decision['tool_calls'])} 个工具调用...")
            
            for call in tool_decision["tool_calls"]:
                tool_name = call.get("tool_name", "")
                arguments = call.get("arguments", {})
                
                # 找到对应的工具信息
                tool_info = None
                for tool in mcp_tools:
                    if tool['tool_name'] == tool_name:
                        tool_info = tool
                        break
                
                if tool_info:
                    # 执行工具调用
                    logger.info(f"调用工具: {tool_name}, 参数: {json.dumps(arguments, ensure_ascii=False)}")
                    call_result = await MCPClientService.call_tool(tool_info, arguments)
                    
                    result["tool_calls"].append({
                        "tool_name": tool_name,
                        "arguments": arguments
                    })
                    result["tool_results"].append({
                        "tool_name": tool_name,
                        "success": call_result.get("success", False),
                        "result": call_result.get("result", ""),
                        "raw_result": call_result.get("raw_result")
                    })
                    
                    logger.info(f"工具 {tool_name} 调用完成: success={call_result.get('success')}")
                else:
                    logger.warning(f"未找到工具: {tool_name}")
                    result["tool_results"].append({
                        "tool_name": tool_name,
                        "success": False,
                        "result": f"未找到工具: {tool_name}"
                    })
            
            # 5. 使用 LLM 整合工具结果生成最终回答
            logger.info("整合工具调用结果生成最终回答...")
            
            tools_result_prompt = f"""用户问题：{question}

工具调用结果：
{json.dumps(result["tool_results"], ensure_ascii=False, indent=2)}

请基于工具调用结果，用自然语言回答用户的问题。要求：
1. 如果工具调用成功，清晰地呈现查询结果
2. 如果工具调用失败，说明原因并给出建议
3. 回答要简洁明了，易于理解"""
            
            result["answer"] = await llm_service.chat(
                prompt=tools_result_prompt,
                system_prompt=system_prompt,
                history=history,
            )
            
            logger.info("工具调用流程完成")
            
        except Exception as e:
            logger.error(f"工具调用流程异常: {e}", exc_info=True)
            result["answer"] = f"抱歉，工具调用过程中出现错误：{str(e)}"
            result["success"] = False
        
        return result

    @staticmethod
    def _parse_tool_decision(response: str) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 返回的工具调用决策
        
        :param response: LLM 响应文本
        :return: 解析后的工具调用决策
        """
        if not response:
            return {"tool_calls": []}
        
        try:
            # 尝试直接解析为 JSON
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 块
        try:
            # 查找第一个 { 开始，最后一个 } 结束的 JSON
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1:
                json_str = response[start:end + 1]
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # 返回空工具调用列表
        return {"tool_calls": []}


# 服务实例
mcp_client_service = MCPClientService()
logger.info("MCP客户端服务实例已创建")
