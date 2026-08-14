from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.crypto import CryptoRecord


class CryptoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self, *, limit: int = 500, offset: int = 0, asset_id: uuid.UUID | None = None
    ) -> tuple[list[CryptoRecord], int]:
        conditions = []
        if asset_id is not None:
            conditions.append(CryptoRecord.asset_id == asset_id)
        total = (
            await self.session.execute(sa.select(sa.func.count(CryptoRecord.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            sa.select(CryptoRecord)
            .where(*conditions)
            .order_by(CryptoRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars()), total

    def add(self, record: CryptoRecord) -> None:
        self.session.add(record)
