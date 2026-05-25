import asyncio
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import hash_password

async def create_admin():
    async for db in get_db():
        result = await db.execute(
            __import__("sqlalchemy").select(User).where(User.username == "admin")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Admin exists: {existing.username} (role={existing.role})")
            return
        user = User(
            username="admin",
            email="admin@imagenious.com",
            password_hash=hash_password("admin123"),
            role="admin",
            quota_remaining=99999,
        )
        db.add(user)
        await db.commit()
        print("Created admin: admin / admin123")

asyncio.run(create_admin())
