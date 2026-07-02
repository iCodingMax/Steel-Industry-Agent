"""
ORM模型基类
单独定义以避免循环导入
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM模型基类"""
    pass
