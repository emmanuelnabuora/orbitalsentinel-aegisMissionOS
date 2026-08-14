"""Audit trail. Called by other services inside their transaction —
the audit row commits atomically with the change it describes."""

import uuid

import structlog

from aegis_api.models.audit import AuditLog
from aegis_api.repositories.audit import AuditRepository


class AuditService:
    def __init__(self, session):
        self.repo = AuditRepository(session)

    def record(
        self,
        *,
        actor_id: uuid.UUID | None,
        action: str,
        resource_type: str | None = None,
        resource_id: uuid.UUID | str | None = None,
        detail: dict | None = None,
    ) -> None:
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        self.repo.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                request_id=request_id,
                detail=detail,
            )
        )
