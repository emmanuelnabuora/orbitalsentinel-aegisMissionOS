from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = sa.select(User).where(sa.func.lower(User.email) == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        total = (await self.session.execute(sa.select(sa.func.count(User.id)))).scalar_one()
        stmt = sa.select(User).order_by(User.created_at).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars()), total

    def add(self, user: User) -> None:
        self.session.add(user)


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revoke_family(self, family_id: uuid.UUID) -> int:
        stmt = (
            sa.update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=sa.func.now())
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    def add(self, token: RefreshToken) -> None:
        self.session.add(token)
