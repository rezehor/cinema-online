import asyncio
from sqlalchemy import select
from models import UserGroup, UserGroupEnum
from database import AsyncPostgresqlSessionLocal

async def seed_user_groups():
    async with AsyncPostgresqlSessionLocal() as session:
        for group_name in UserGroupEnum:
            stmt = select(UserGroup).where(UserGroup.name == group_name)
            result = await session.execute(stmt)
            if not result.scalar():
                session.add(UserGroup(name=group_name))
                print(f"Added user group: {group_name}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_user_groups())
