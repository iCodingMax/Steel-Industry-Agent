"""
对话用户服务模块
处理对话用户的业务逻辑

主要功能：
1. 对话用户CRUD操作
2. 从OAuth2同步对话用户
3. 对话用户状态管理
4. 对话用户密码管理
"""
from typing import Optional, Tuple
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_user import ChatUser
from app.schemas.chat_user import ChatUserCreate, ChatUserUpdate, ChatUserQuery
from app.utils.security import hash_password, verify_password


class ChatUserService:
    """对话用户服务类"""

    async def list_users(
        self,
        db: AsyncSession,
        query: ChatUserQuery,
    ) -> Tuple[int, list[ChatUser]]:
        """
        获取对话用户列表
        
        :param db: 数据库会话
        :param query: 查询参数
        :return: (总数, 用户列表)
        """
        conditions = []
        
        if query.keyword:
            keyword = f"%{query.keyword}%"
            conditions.append(
                func.lower(ChatUser.username).like(keyword) |
                func.lower(ChatUser.name).like(keyword) |
                func.lower(ChatUser.email).like(keyword)
            )
        
        if query.status:
            conditions.append(ChatUser.status == query.status)
        
        # 查询总数
        count_stmt = select(func.count(ChatUser.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total = await db.execute(count_stmt)
        total = total.scalar() or 0
        
        # 查询列表
        stmt = select(ChatUser)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(ChatUser.created_at.desc())
        stmt = stmt.offset((query.page - 1) * query.pageSize).limit(query.pageSize)
        
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        return total, users

    async def get_user_by_id(
        self, db: AsyncSession, user_id: int
    ) -> Optional[ChatUser]:
        """
        根据ID获取对话用户
        
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 用户对象或None
        """
        stmt = select(ChatUser).where(ChatUser.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username(
        self, db: AsyncSession, username: str
    ) -> Optional[ChatUser]:
        """
        根据用户名获取对话用户
        
        :param db: 数据库会话
        :param username: 用户名
        :return: 用户对象或None
        """
        stmt = select(ChatUser).where(ChatUser.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self, db: AsyncSession, data: ChatUserCreate
    ) -> ChatUser:
        """
        创建对话用户
        
        :param db: 数据库会话
        :param data: 用户数据
        :return: 创建的用户对象
        """
        # 检查用户名是否已存在
        existing = await self.get_user_by_username(db, data.username)
        if existing:
            raise ValueError(f"用户名 {data.username} 已存在")
        
        user = ChatUser(
            username=data.username,
            name=data.name,
            email=data.email,
            phone=data.phone,
            password_hash=hash_password("123456"),  # 默认密码123456
            status=data.status,
            user_source="local",
            force_change_password=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"创建对话用户成功(默认密码123456): {user.username}")
        return user

    async def update_user(
        self, db: AsyncSession, user_id: int, data: ChatUserUpdate
    ) -> Optional[ChatUser]:
        """
        更新对话用户
        
        :param db: 数据库会话
        :param user_id: 用户ID
        :param data: 更新数据
        :return: 更新后的用户对象或None
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"更新对话用户成功: {user.username}")
        return user

    async def delete_user(
        self, db: AsyncSession, user_id: int
    ) -> bool:
        """
        删除对话用户
        
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 是否删除成功
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return False
        
        await db.delete(user)
        await db.commit()
        
        logger.info(f"删除对话用户成功: {user.username}")
        return True

    async def reset_password(
        self, db: AsyncSession, user_id: int, new_password: str = "123456"
    ) -> bool:
        """
        重置对话用户密码（默认重置为123456）
        
        :param db: 数据库会话
        :param user_id: 用户ID
        :param new_password: 新密码，默认123456
        :return: 是否重置成功
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return False
        
        user.password_hash = hash_password(new_password)
        user.force_change_password = new_password == "123456"  # 默认密码强制修改
        await db.commit()
        
        logger.info(f"重置对话用户密码成功: {user.username}")
        return True

    async def toggle_status(
        self, db: AsyncSession, user_id: int
    ) -> Optional[ChatUser]:
        """
        切换用户状态
        
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 更新后的用户对象或None
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return None
        
        user.status = "disabled" if user.status == "active" else "active"
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"切换用户状态成功: {user.username} -> {user.status}")
        return user

    async def sync_oauth_user(
        self, db: AsyncSession, oauth_user_info: dict
    ) -> ChatUser:
        """
        从OAuth2同步对话用户
        
        :param db: 数据库会话
        :param oauth_user_info: OAuth2返回的用户信息
        :return: 同步后的用户对象
        """
        username = oauth_user_info.get("username", "")
        if not username:
            raise ValueError("用户名不能为空")
        
        # 查找现有用户
        user = await self.get_user_by_username(db, username)
        
        if user:
            # 更新现有用户信息
            name = oauth_user_info.get("name")
            email = oauth_user_info.get("email")
            phone = oauth_user_info.get("phone")
            
            if name and name != user.name:
                user.name = name
            if email and email != user.email:
                user.email = email
            if phone and phone != user.phone:
                user.phone = phone
            user.status = "active"
            user.user_source = "oauth2"
        else:
            # 创建新用户（默认密码123456）
            user = ChatUser(
                username=username,
                name=oauth_user_info.get("name"),
                email=oauth_user_info.get("email"),
                phone=oauth_user_info.get("phone"),
                password_hash=hash_password("123456"),
                status="active",
                user_source="oauth2",
                force_change_password=True,
            )
            db.add(user)
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"OAuth2同步对话用户成功: {user.username}")
        return user


# 创建全局实例
chat_user_service = ChatUserService()
