"""
OAuth2服务模块
处理OAuth2统一认证相关操作

主要功能：
1. OAuth2配置管理：按类型（system/chat）读取和更新OAuth2配置
2. OAuth2登录：通过OAuth2认证中心登录用户
3. 用户同步：OAuth2登录时自动创建/更新本地用户

配置类型：
- system: 系统用户配置（登录工业智能助手平台的用户）
- chat: 对话用户配置（发布应用集成的业务系统用户）

认证流程：
1. 前端跳转到授权端获取授权码(code)
2. 回调页面收到code，发送到后端
3. 后端用code换取access_token
4. 用access_token获取用户信息
5. 根据字段映射创建/更新本地用户
6. 返回平台JWT令牌
"""
import json
from datetime import datetime
from urllib.parse import urlencode

import aiohttp
from typing import Optional, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.oauth_config import OAuthConfig
from app.models.user import User
from app.models.chat_user import ChatUser
from app.schemas.oauth import OAuthConfigUpdate
from app.utils.security import hash_password, create_access_token
from app.core.config import settings
from app.middlewares.exception_handler import BusinessException

# 配置类型常量
CONFIG_TYPE_SYSTEM = "system"  # 系统用户配置
CONFIG_TYPE_CHAT = "chat"      # 对话用户配置


class OAuthService:
    """
    OAuth2服务类
    负责OAuth2配置管理和认证流程
    """

    @staticmethod
    async def get_config(db: AsyncSession, config_type: str = CONFIG_TYPE_SYSTEM) -> Optional[OAuthConfig]:
        """
        按类型获取OAuth2配置
        
        :param db: 数据库会话
        :param config_type: 配置类型 (system/chat)
        :return: OAuth配置对象
        """
        stmt = select(OAuthConfig).where(OAuthConfig.config_type == config_type)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def save_config(db: AsyncSession, data: OAuthConfigUpdate) -> OAuthConfig:
        """
        保存OAuth2配置（按类型区分）
        
        :param db: 数据库会话
        :param data: 配置更新数据
        :return: 更新后的配置
        """
        config_type = data.configType
        config = await OAuthService.get_config(db, config_type)
        
        field_mapping_json = json.dumps(data.fieldMapping or {}, ensure_ascii=False)
        
        if config:
            # 更新现有配置
            config.authorization_url = data.authorizationUrl
            config.token_url = data.tokenUrl
            config.user_info_url = data.userInfoUrl
            config.scope = data.scope
            config.client_id = data.clientId
            config.client_secret = data.clientSecret
            config.field_mapping = field_mapping_json
            config.redirect_url = data.redirectUrl
            config.enabled = data.enabled
        else:
            # 创建新配置
            config = OAuthConfig(
                config_type=config_type,
                authorization_url=data.authorizationUrl,
                token_url=data.tokenUrl,
                user_info_url=data.userInfoUrl,
                scope=data.scope,
                client_id=data.clientId,
                client_secret=data.clientSecret,
                field_mapping=field_mapping_json,
                redirect_url=data.redirectUrl,
                enabled=data.enabled,
            )
            db.add(config)
        
        await db.commit()
        await db.refresh(config)
        logger.info(f"OAuth2配置保存成功，类型: {config_type}, 启用状态: {data.enabled}")
        return config

    @staticmethod
    async def is_enabled(db: AsyncSession, config_type: str = CONFIG_TYPE_SYSTEM) -> bool:
        """
        检查指定类型的OAuth2是否启用
        
        :param db: 数据库会话
        :param config_type: 配置类型
        :return: 是否启用
        """
        config = await OAuthService.get_config(db, config_type)
        return config is not None and config.enabled

    @staticmethod
    def build_authorization_url(config: OAuthConfig, state: str = "", origin: str = "") -> str:
        """
        构建OAuth2授权URL
        
        :param config: OAuth2配置
        :param state: 状态参数（用于防止CSRF）
        :param origin: 请求来源（用于动态构建回调URL的主机部分）
        :return: 授权URL
        """
        # 根据请求来源动态构建回调URL的主机部分
        redirect_url = config.redirect_url
        if origin and config.redirect_url:
            # 从配置的redirect_url中提取路径部分
            from urllib.parse import urlparse
            parsed = urlparse(config.redirect_url)
            if parsed.path:
                # 使用请求的origin替换配置中的主机部分
                redirect_url = f"{origin}{parsed.path}"
                if parsed.query:
                    redirect_url += f"?{parsed.query}"
        
        params = {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": redirect_url,
            "scope": config.scope,
        }
        if state:
            params["state"] = state
        
        # 使用 urlencode 对参数值进行 URL 编码（特别是 redirect_uri 中的 :// 和 /）
        # 符合 RFC 6749 规范
        query_string = urlencode(params)
        return f"{config.authorization_url}?{query_string}"

    @staticmethod
    async def exchange_code_for_token(
        config: OAuthConfig, code: str
    ) -> Optional[str]:
        """
        用授权码换取访问令牌
        
        :param config: OAuth2配置
        :param code: 授权码
        :return: 访问令牌
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config.token_url,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": config.client_id,
                        "client_secret": config.client_secret,
                        "redirect_uri": config.redirect_url,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("access_token")
                    else:
                        error_text = await resp.text()
                        logger.error(f"获取访问令牌失败: status={resp.status}, body={error_text}")
                        return None
        except Exception as e:
            logger.error(f"换取访问令牌异常: {e}")
            return None

    @staticmethod
    async def get_user_info(
        config: OAuthConfig, access_token: str
    ) -> Optional[Dict]:
        """
        获取用户信息
        
        :param config: OAuth2配置
        :param access_token: 访问令牌
        :return: 用户信息字典
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.user_info_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        user_info = await resp.json()
                        # 记录 OAuth 返回的原始用户信息，便于排查字段映射问题
                        logger.info(f"OAuth 返回用户信息: {json.dumps(user_info, ensure_ascii=False)}")
                        return user_info
                    else:
                        error_text = await resp.text()
                        logger.error(f"获取用户信息失败: status={resp.status}, body={error_text}")
                        return None
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return None

    # 本系统字段名与 User 模型字段的映射关系
    # key: 配置中的本系统字段名
    # value: User 模型中的实际字段名
    SYSTEM_FIELD_MAP = {
        "username": "username",
        "nick_name": "name",      # 昵称 -> 姓名
        "nickname": "name",
        "name": "name",
        "email": "email",
        "phone": "phone",
    }

    # 手机号可能的字段名列表（用于回退查找）
    PHONE_FIELD_CANDIDATES = ["phone", "mobile", "phoneNumber", "phone_number", "mobile_number"]

    @staticmethod
    def _find_nested_value(data: Dict, key: str) -> Optional:
        """
        递归查找嵌套字典中的指定 key
        
        :param data: 字典数据
        :param key: 要查找的 key
        :return: 找到的值或 None
        """
        if not isinstance(data, dict):
            return None
        if key in data:
            value = data[key]
            if value is not None and value != "":
                return value
        # 递归查找嵌套的字典
        for k, v in data.items():
            if isinstance(v, dict):
                result = OAuthService._find_nested_value(v, key)
                if result is not None:
                    return result
        return None

    @staticmethod
    def map_user_fields(
        oauth_user_info: Dict, config: OAuthConfig
    ) -> Dict:
        """
        根据字段映射转换用户信息
        
        映射格式：{"本系统字段": "认证中心字段"}
        例如：{"username":"preferred_username", "nick_name":"nickname", "email":"email", "phone":"phone"}
        
        :param oauth_user_info: OAuth2返回的用户信息
        :param config: OAuth2配置
        :return: 映射后的用户信息（包含 username, name, email, phone 等）
        """
        try:
            field_mapping = json.loads(config.field_mapping) if config.field_mapping else {}
        except (json.JSONDecodeError, TypeError):
            field_mapping = {}

        logger.info(f"开始字段映射，配置映射: {field_mapping}")
        logger.info(f"OAuth 返回可用字段: {list(oauth_user_info.keys())}")

        # 初始化映射结果，使用 User 模型的字段名作为 key
        mapped_info = {
            "username": "",
            "name": "",
            "email": "",
            "phone": "",
        }

        # 按照配置映射进行字段转换
        # field_mapping 格式: {"本系统字段": "认证中心字段"}
        for system_field, oauth_field in field_mapping.items():
            # 获取认证中心的字段值（先在顶层查找）
            value = oauth_user_info.get(oauth_field)
            logger.debug(f"映射: 系统字段[{system_field}] <- 认证字段[{oauth_field}]: 顶层值={value}")

            # 如果顶层未找到，尝试递归查找嵌套结构
            if value is None or value == "":
                logger.debug(f"  顶层未找到，尝试递归查找嵌套结构...")
                value = OAuthService._find_nested_value(oauth_user_info, oauth_field)
                if value is not None:
                    logger.debug(f"  从嵌套结构中找到: {value}")

            # 仍然为空则跳过
            if value is None or value == "":
                logger.debug(f"  跳过空值")
                continue

            value_str = str(value)

            # 将本系统字段名映射到 User 模型字段名
            user_field = OAuthService.SYSTEM_FIELD_MAP.get(system_field, system_field)
            if user_field in mapped_info:
                mapped_info[user_field] = value_str
            else:
                # 未知字段也记录下来，便于扩展
                mapped_info[system_field] = value_str

        # 回退逻辑：如果映射未获取到 username，尝试从常用字段获取
        if not mapped_info["username"]:
            mapped_info["username"] = (
                oauth_user_info.get("preferred_username")
                or oauth_user_info.get("username")
                or oauth_user_info.get("sub")
                or ""
            )

        # 回退逻辑：如果映射未获取到 name
        if not mapped_info["name"]:
            # 尝试从嵌套结构中查找
            name_value = (
                oauth_user_info.get("nickname")
                or oauth_user_info.get("name")
                or OAuthService._find_nested_value(oauth_user_info, "nickname")
                or OAuthService._find_nested_value(oauth_user_info, "name")
                or mapped_info["username"]
                or ""
            )
            if name_value and str(name_value) != "None":
                mapped_info["name"] = str(name_value)

        # 回退逻辑：如果映射未获取到 email
        if not mapped_info["email"]:
            email_value = (
                oauth_user_info.get("email")
                or OAuthService._find_nested_value(oauth_user_info, "email")
                or ""
            )
            if email_value:
                mapped_info["email"] = str(email_value)

        # 回退逻辑：如果映射未获取到 phone，尝试多个可能的字段名
        if not mapped_info["phone"]:
            for phone_field in OAuthService.PHONE_FIELD_CANDIDATES:
                phone_value = (
                    oauth_user_info.get(phone_field)
                    or OAuthService._find_nested_value(oauth_user_info, phone_field)
                )
                if phone_value and str(phone_value) != "None":
                    mapped_info["phone"] = str(phone_value)
                    logger.info(f"回退逻辑：从字段 [{phone_field}] 获取手机号: {mapped_info['phone']}")
                    break

        logger.info(f"字段映射完成: {json.dumps(mapped_info, ensure_ascii=False)}")
        return mapped_info

    @staticmethod
    async def login_or_create_user(
        db: AsyncSession, user_info: Dict, config: OAuthConfig
    ) -> Optional[User]:
        """
        系统用户登录或创建（OAuth2登录平台时调用）
        
        :param db: 数据库会话
        :param user_info: 映射后的用户信息
        :param config: OAuth2配置
        :return: 用户对象
        """
        username = user_info.get("username", "")
        if not username:
            logger.error("OAuth2登录失败: 无法获取用户名")
            return None

        logger.info(f"查找系统用户: username={username}")
        
        # 查找现有系统用户
        from sqlalchemy import select as sa_select
        stmt = sa_select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            await db.refresh(user)
            
            field_mapping = {
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "phone": user_info.get("phone"),
            }
            
            updates = {}
            for field, new_value in field_mapping.items():
                if not new_value:
                    continue
                old_value = user.__dict__.get(field)
                if str(new_value) != str(old_value or ""):
                    updates[field] = new_value
            
            if updates:
                for field, value in updates.items():
                    setattr(user, field, value)
            
            user.user_source = "oauth2"
            user.oauth_provider = config.client_id
        else:
            # OAuth2创建的系统用户，默认密码为123456
            default_password = "123456"
            
            user = User(
                username=username,
                name=user_info.get("name") or "",
                email=user_info.get("email") or "",
                phone=user_info.get("phone") or "",
                password_hash=hash_password(default_password),
                role="user",
                status="active",
                user_source="oauth2",
                oauth_provider=config.client_id,
                force_change_password=True,
            )
            db.add(user)
            logger.info(f"创建OAuth2系统用户(默认密码123456): username={username}")

        await db.commit()
        await db.refresh(user)
        logger.info(f"系统用户OAuth2登录/创建成功: {user.username}")
        return user

    @staticmethod
    async def chat_login_or_create_user(
        db: AsyncSession, user_info: Dict, config: OAuthConfig
    ) -> Optional[ChatUser]:
        """
        对话用户登录或创建（对话用户OAuth2登录时调用）
        
        :param db: 数据库会话
        :param user_info: 映射后的用户信息
        :param config: OAuth2配置
        :return: 对话用户对象
        """
        username = user_info.get("username", "")
        if not username:
            logger.error("对话用户OAuth2登录失败: 无法获取用户名")
            return None

        logger.info(f"查找对话用户: username={username}")
        
        # 查找现有对话用户
        from sqlalchemy import select as sa_select
        stmt = sa_select(ChatUser).where(ChatUser.username == username)
        result = await db.execute(stmt)
        chat_user = result.scalar_one_or_none()

        if chat_user:
            await db.refresh(chat_user)
            
            field_mapping = {
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "phone": user_info.get("phone"),
            }
            
            updates = {}
            for field, new_value in field_mapping.items():
                if not new_value:
                    continue
                old_value = chat_user.__dict__.get(field)
                if str(new_value) != str(old_value or ""):
                    updates[field] = new_value
            
            if updates:
                for field, value in updates.items():
                    setattr(chat_user, field, value)
            
            chat_user.last_login_at = datetime.utcnow()
            logger.info(f"更新对话用户: username={username}, updates={updates}")
        else:
            chat_user = ChatUser(
                username=username,
                name=user_info.get("name") or "",
                email=user_info.get("email") or "",
                phone=user_info.get("phone") or "",
                status="active",
                user_source="oauth2",
                last_login_at=datetime.utcnow(),
            )
            db.add(chat_user)
            logger.info(f"创建对话用户: username={username}")

        await db.commit()
        await db.refresh(chat_user)
        logger.info(f"对话用户OAuth2登录/创建成功: {chat_user.username}")
        return chat_user

    @staticmethod
    def generate_platform_token(user: User) -> Dict:
        """
        生成平台JWT令牌（用于系统用户登录）
        
        :param user: 用户对象
        :return: 令牌信息
        """
        from datetime import timedelta
        token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {
            "token": token,
            "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    @staticmethod
    def generate_chat_token(chat_user: ChatUser) -> Dict:
        """
        生成对话用户令牌（用于应用集成）
        
        :param chat_user: 对话用户对象
        :return: 令牌信息
        """
        from datetime import timedelta
        token = create_access_token(
            data={"sub": chat_user.username, "chat_user_id": chat_user.id, "type": "chat"},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {
            "token": token,
            "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }


# 服务实例
oauth_service = OAuthService()
logger.info("OAuth2服务实例已创建")
