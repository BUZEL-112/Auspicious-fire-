from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.db.models import User


class UserRepository:
    """Repository handling database operations for User records."""

    async def get_by_id(self, session: AsyncSession, user_id: str) -> Optional[User]:
        """Fetch a user record by primary key."""
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, user: User) -> User:
        """Persist a new user record."""
        session.add(user)
        await session.flush()
        return user

    async def create_or_get(
        self,
        session: AsyncSession,
        user_id: str,
        display_name: Optional[str] = None,
        default_city: Optional[str] = None,
        default_style: Optional[str] = None,
    ) -> User:
        """Fetch an existing user or create a new user record."""
        user = await self.get_by_id(session, user_id)
        if user is not None:
            return user

        new_user = User(
            user_id=user_id,
            display_name=display_name or user_id,
            default_city=default_city,
            default_style=default_style,
        )
        session.add(new_user)
        await session.flush()
        return new_user
