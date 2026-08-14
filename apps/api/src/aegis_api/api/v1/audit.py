"""Audit trail (read-only): platform admins and auditors."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aegis_api.api.deps import SessionDep, require_permission
from aegis_api.core.permissions import Permission
from aegis_api.models.user import User
from aegis_api.repositories.audit import AuditRepository
from aegis_api.schemas.audit import AuditEntryRead

router = APIRouter(prefix="/audit", tags=["audit"])

Auditor = Annotated[User, Depends(require_permission(Permission.AUDIT_READ))]


@router.get("", response_model=list[AuditEntryRead])
async def recent_audit_log(
    session: SessionDep,
    _: Auditor,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AuditEntryRead]:
    entries = await AuditRepository(session).list_recent(limit=limit)
    return [AuditEntryRead.model_validate(e) for e in entries]
