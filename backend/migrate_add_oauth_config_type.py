"""
数据库迁移脚本：为oauth_config表添加config_type字段

执行方式：python migrate_add_oauth_config_type.py
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import system_engine
from sqlalchemy import text


async def migrate():
    """执行迁移"""
    print("开始迁移：为oauth_config表添加config_type字段...")
    
    try:
        async with system_engine.begin() as conn:
            # 检查config_type列是否已存在
            result = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'oauth_config' AND column_name = 'config_type')"
            ))
            exists = result.scalar()
            
            if not exists:
                # 添加config_type列
                await conn.execute(text(
                    "ALTER TABLE oauth_config ADD COLUMN config_type VARCHAR(20) NOT NULL DEFAULT 'system'"
                ))
                print("  ✓ 成功添加config_type列")
                
                # 将现有配置的config_type设置为system
                await conn.execute(text(
                    "UPDATE oauth_config SET config_type = 'system' WHERE config_type IS NULL OR config_type = ''"
                ))
                print("  ✓ 成功将现有配置标记为system类型")
            else:
                print("  - config_type列已存在，跳过")
            
            # 检查是否存在chat类型的配置
            result = await conn.execute(text(
                "SELECT COUNT(*) FROM oauth_config WHERE config_type = 'chat'"
            ))
            chat_count = result.scalar()
            
            if chat_count == 0:
                print("  - 尚未创建对话用户OAuth配置，将在用户配置时自动创建")
    
    except Exception as e:
        print(f"  ✗ 迁移失败：{e}")
        raise
    
    print("迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
