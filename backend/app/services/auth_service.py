"""
认证服务
"""
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user import User
from app.schemas.auth import LoginRequest, ChangePasswordRequest
from app.utils.security import hash_password, verify_password, create_access_token, decode_token
from app.core.config import settings
from app.middlewares.exception_handler import BusinessException


class AuthService:
    """认证服务类"""

    @staticmethod
    async def login(db: AsyncSession, req: LoginRequest) -> dict:
        """用户登录"""
        stmt = select(User).where(User.username == req.username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"用户不存在: {req.username}")
            raise BusinessException(code=401, message="用户名或密码错误")

        if not verify_password(req.password, user.password_hash):
            logger.warning(f"密码验证失败: {req.username}")
            raise BusinessException(code=401, message="用户名或密码错误")

        from datetime import datetime
        user.last_login_at = datetime.utcnow()
        await db.commit()

        token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info(f"用户登录成功: {user.username}")

        return {
            "token": token,
            "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user.to_dict(),
        }

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        """根据ID获取用户"""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
        """根据用户名获取用户"""
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def change_password(
        db: AsyncSession, user_id: int, req: ChangePasswordRequest
    ) -> None:
        """修改密码"""
        user = await AuthService.get_user_by_id(db, user_id)
        if not user:
            raise BusinessException(code=404, message="用户不存在")

        if not verify_password(req.oldPassword, user.password_hash):
            raise BusinessException(code=400, message="原密码错误")

        user.password_hash = hash_password(req.newPassword)
        user.force_change_password = False
        await db.commit()
        logger.info(f"用户修改密码成功: {user.username}")

    @staticmethod
    async def init_default_admin(db: AsyncSession) -> None:
        """初始化默认admin用户"""
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


auth_service = AuthService()
