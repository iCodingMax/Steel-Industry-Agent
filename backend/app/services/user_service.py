"""
用户管理服务模块
处理用户CRUD操作、密码管理等功能

主要功能：
1. 用户管理：创建、查询、更新、删除用户
2. 密码重置：管理员可以重置任意用户密码
3. 状态管理：启用/禁用用户账号
4. OAuth同步：支持从统一认证中心同步用户

安全机制：
- 创建用户时密码自动加密存储
- 不允许删除自己的账号
- 禁用状态的用户无法登录
"""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import hash_password
from app.middlewares.exception_handler import BusinessException


class UserService:
    """
    用户服务类
    负责系统用户的生命周期管理
    """

    @staticmethod
    async def create(db: AsyncSession, data: UserCreate) -> User:
        """
        创建用户

        :param db: 数据库会话
        :param data: 用户创建参数
        :return: 创建的用户对象
        :raises BusinessException: 用户名已存在时抛出
        """
        logger.debug(f"创建用户: username={data.username}")

        # 校验用户名唯一性
        existing = await UserService.get_by_username(db, data.username)
        if existing:
            raise BusinessException(code=400, message=f"用户名已存在: {data.username}")

        user = User(
            username=data.username,
            name=data.name,
            email=data.email,
            phone=data.phone,
            password_hash=hash_password(data.password),
            role=data.role,
            status="active",
            force_change_password=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"创建用户成功: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
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
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
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
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """
        获取用户列表（支持分页和搜索）

        :param db: 数据库会话
        :param page: 页码
        :param page_size: 每页条数
        :param keyword: 搜索关键词（匹配用户名、姓名、邮箱）
        :param status: 状态筛选
        :return: (用户列表, 总数)
        """
        skip = (page - 1) * page_size

        # 构建查询
        query = select(User)
        count_query = select(func.count(User.id))

        # 关键词搜索
        if keyword:
            keyword_like = f"%{keyword}%"
            query = query.where(
                User.username.like(keyword_like)
                | User.name.like(keyword_like)
                | User.email.like(keyword_like)
            )
            count_query = count_query.where(
                User.username.like(keyword_like)
                | User.name.like(keyword_like)
                | User.email.like(keyword_like)
            )

        # 状态筛选
        if status:
            query = query.where(User.status == status)
            count_query = count_query.where(User.status == status)

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        query = query.order_by(User.id.desc()).offset(skip).limit(page_size)
        result = await db.execute(query)
        users = list(result.scalars().all())

        return users, total

    @staticmethod
    async def update(db: AsyncSession, user_id: int, data: UserUpdate) -> Optional[User]:
        """
        更新用户信息

        :param db: 数据库会话
        :param user_id: 用户ID
        :param data: 更新参数
        :return: 更新后的用户对象
        :raises BusinessException: 用户不存在时抛出
        """
        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise BusinessException(code=404, message="用户不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        await db.commit()
        await db.refresh(user)
        logger.info(f"更新用户成功: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def delete(db: AsyncSession, user_id: int, current_user_id: int) -> None:
        """
        删除用户

        :param db: 数据库会话
        :param user_id: 待删除的用户ID
        :param current_user_id: 当前操作人的ID（防止删除自己）
        :raises BusinessException: 用户不存在或删除自己时抛出
        """
        if user_id == current_user_id:
            raise BusinessException(code=400, message="不能删除自己的账号")

        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise BusinessException(code=404, message="用户不存在")

        # 不允许删除admin账号
        if user.username == "admin":
            raise BusinessException(code=400, message="不能删除管理员账号")

        from sqlalchemy import text

        # 1. 删除关联的会话数据（含消息、溯源等通过外键级联）
        # 注意：系统用户与对话用户（chat_users）独立，删除系统用户不影响对话用户
        try:
            # 先删除 traces（引用 sessions.id）
            await db.execute(
                text("DELETE FROM traces WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :uid)"),
                {"uid": user_id}
            )
            # 再删除 messages（引用 sessions.id）
            await db.execute(
                text("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :uid)"),
                {"uid": user_id}
            )
            # 最后删除 sessions
            await db.execute(
                text("DELETE FROM sessions WHERE user_id = :uid"),
                {"uid": user_id}
            )
        except Exception as e:
            logger.warning(f"清理关联会话数据失败: {e}")

        # 2. 解除 applications 和 knowledge 的外键引用（设置为NULL）
        try:
            await db.execute(
                text("UPDATE applications SET created_by = NULL WHERE created_by = :uid"),
                {"uid": user_id}
            )
            await db.execute(
                text("UPDATE knowledge_bases SET created_by = NULL WHERE created_by = :uid"),
                {"uid": user_id}
            )
        except Exception as e:
            logger.warning(f"解除应用/知识库外键引用失败: {e}")

        # 3. flush所有待处理操作
        await db.flush()

        # 4. 使用原生SQL删除用户，确保DELETE语句被执行
        result = await db.execute(
            text("DELETE FROM users WHERE id = :uid"),
            {"uid": user_id}
        )
        await db.commit()

        if result.rowcount == 0:
            logger.warning(f"用户删除SQL未影响任何行: {user.username} (ID: {user_id})")
        else:
            logger.info(f"删除用户成功: {user.username} (ID: {user_id}), 影响行数: {result.rowcount}")

    @staticmethod
    async def reset_password(db: AsyncSession, user_id: int, new_password: str) -> None:
        """
        重置用户密码

        :param db: 数据库会话
        :param user_id: 用户ID
        :param new_password: 新密码
        :raises BusinessException: 用户不存在时抛出
        """
        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise BusinessException(code=404, message="用户不存在")

        user.password_hash = hash_password(new_password)
        user.force_change_password = False
        await db.commit()

        logger.info(f"重置用户密码成功: {user.username} (ID: {user_id})")

    @staticmethod
    async def toggle_status(db: AsyncSession, user_id: int) -> Optional[User]:
        """
        切换用户状态（启用/禁用）

        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 更新后的用户对象
        :raises BusinessException: 用户不存在时抛出
        """
        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise BusinessException(code=404, message="用户不存在")

        # 不允许禁用admin账号
        if user.username == "admin":
            raise BusinessException(code=400, message="不能禁用管理员账号")

        user.status = "disabled" if user.status == "active" else "active"
        await db.commit()
        await db.refresh(user)
        logger.info(f"切换用户状态: {user.username} -> {user.status}")
        return user


# 服务实例
user_service = UserService()
logger.info("用户管理服务实例已创建")
