import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.audit import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, entry: AuditLog) -> None:
        self.session.add(entry)

    async def list_recent(self, *, limit: int = 50) -> list[AuditLog]:
        stmt = sa.select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars())
