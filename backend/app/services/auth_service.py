"""
认证服务模块
处理用户认证和授权相关操作

主要功能：
1. 用户登录：验证用户名密码，生成JWT令牌
2. 用户查询：根据ID或用户名获取用户信息
3. 修改密码：验证原密码后更新新密码
4. 默认管理员：初始化默认admin用户（首次启动时自动调用）

安全机制：
- 密码使用bcrypt加密存储
- 使用JWT进行无状态认证
- 登录失败记录日志（便于安全审计）
- 默认admin用户强制要求首次登录修改密码
"""
from datetime import timedelta, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user import User
from app.schemas.auth import LoginRequest, ChangePasswordRequest
from app.utils.security import hash_password, verify_password, create_access_token, decode_token
from app.core.config import settings
from app.middlewares.exception_handler import BusinessException


class AuthService:
    """
    认证服务类
    负责用户登录、密码管理和JWT令牌生成
    """

    @staticmethod
    async def login(db: AsyncSession, req: LoginRequest) -> dict:
        """
        用户登录

        :param db: 数据库会话
        :param req: 登录请求（包含username和password）
        :return: 登录结果，包含token、expiresIn和user信息
        :raises BusinessException: 用户名或密码错误时抛出
        """
        logger.debug(f"用户登录请求: {req.username}")

        # 查询用户
        stmt = select(User).where(User.username == req.username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        # 用户不存在
        if not user:
            logger.warning(f"用户登录失败: 用户不存在 - {req.username}")
            raise BusinessException(code=401, message="用户名或密码错误")

        # 密码验证失败
        if not verify_password(req.password, user.password_hash):
            logger.warning(f"用户登录失败: 密码错误 - {req.username}")
            raise BusinessException(code=401, message="用户名或密码错误")

        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        await db.commit()

        # 生成JWT令牌
        token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info(f"用户登录成功: {user.username}, 角色={user.role}")

        return {
            "token": token,
            "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user.to_dict(),
        }

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        """
        根据ID获取用户

        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 用户对象（不存在返回None）
        """
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
        """
        根据用户名获取用户

        :param db: 数据库会话
        :param username: 用户名
        :return: 用户对象（不存在返回None）
        """
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def change_password(
        db: AsyncSession, user_id: int, req: ChangePasswordRequest
    ) -> None:
        """
        修改密码

        :param db: 数据库会话
        :param user_id: 用户ID
        :param req: 修改密码请求（包含oldPassword和newPassword）
        :raises BusinessException: 用户不存在或原密码错误时抛出
        """
        user = await AuthService.get_user_by_id(db, user_id)
        if not user:
            raise BusinessException(code=404, message="用户不存在")

        # 验证原密码
        if not verify_password(req.oldPassword, user.password_hash):
            raise BusinessException(code=400, message="原密码错误")

        # 更新密码并取消强制修改密码标志
        user.password_hash = hash_password(req.newPassword)
        user.force_change_password = False
        await db.commit()

        logger.info(f"用户修改密码成功: {user.username}")

    @staticmethod
    async def init_default_admin(db: AsyncSession) -> None:
        """
        初始化默认admin用户
        首次启动时自动调用，创建admin/admin账号
        默认强制要求首次登录修改密码

        :param db: 数据库会话
        """
        existing = await AuthService.get_user_by_username(db, "admin")
        if existing:
            logger.info("默认admin用户已存在，跳过初始化")
            return

        admin = User(
            username="admin",
            password_hash=hash_password("admin"),
            role="admin",
            force_change_password=True,
        )
        db.add(admin)
        await db.commit()

        logger.success("默认admin用户初始化成功 (admin/admin)")
        logger.warning("请在首次登录后修改默认密码")


# 服务实例
auth_service = AuthService()
logger.info("认证服务实例已创建")
