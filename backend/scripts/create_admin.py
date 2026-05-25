"""
创建管理员账号脚本

用法:
    cd backend
    python -m scripts.create_admin

或指定参数:
    python -m scripts.create_admin --username admin --email admin@example.com --password admin123
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.user import User
from app.services.auth_service import hash_password


async def create_admin(username: str = "admin", email: str = "admin@imagenious.com", password: str = "admin123"):
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.role == "admin"))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"管理员账号已存在: {existing.username} ({existing.email})")
            update = input("是否重置密码? (y/N): ").strip().lower()
            if update == "y":
                existing.password_hash = hash_password(password)
                await session.commit()
                print(f"密码已重置为: {password}")
            return

        result = await session.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"用户名 '{username}' 已被占用，请使用其他用户名")
            return

        result = await session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"邮箱 '{email}' 已被注册，请使用其他邮箱")
            return

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            quota_remaining=99999,
        )
        session.add(user)
        await session.commit()

        print("=" * 50)
        print("管理员账号创建成功!")
        print(f"  用户名: {username}")
        print(f"  邮箱:   {email}")
        print(f"  密码:   {password}")
        print(f"  角色:   admin")
        print("=" * 50)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="创建管理员账号")
    parser.add_argument("--username", default="admin", help="管理员用户名")
    parser.add_argument("--email", default="admin@imagenious.com", help="管理员邮箱")
    parser.add_argument("--password", default="admin123", help="管理员密码")
    args = parser.parse_args()

    asyncio.run(create_admin(args.username, args.email, args.password))
