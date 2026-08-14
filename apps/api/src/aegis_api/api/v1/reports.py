import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from aegis_api.api.deps import CurrentUser, SessionDep, require_roles
from aegis_api.models.enums import ReportKind, Role
from aegis_api.models.user import User
from aegis_api.schemas.common import Page
from aegis_api.schemas.report import ReportDetail, ReportGenerate, ReportRead
from aegis_api.services.report_pdf import render_report_pdf
from aegis_api.services.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

Author = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.ANALYST))]


@router.post("", response_model=ReportDetail, status_code=status.HTTP_201_CREATED)
async def generate_report(body: ReportGenerate, session: SessionDep, actor: Author) -> ReportDetail:
    report = await ReportService(session).generate(body, actor_id=actor.id)
    return ReportDetail.model_validate(report)


@router.get("", response_model=Page[ReportRead])
async def list_reports(
    session: SessionDep,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: ReportKind | None = None,
) -> Page[ReportRead]:
    reports, total = await ReportService(session).list(limit=limit, offset=offset, kind=kind)
    return Page(
        items=[ReportRead.model_validate(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(report_id: uuid.UUID, session: SessionDep, _: CurrentUser) -> ReportDetail:
    return ReportDetail.model_validate(await ReportService(session).get(report_id))


@router.get("/{report_id}/export.pdf")
async def export_report_pdf(report_id: uuid.UUID, session: SessionDep, _: CurrentUser) -> Response:
    report = await ReportService(session).get(report_id)
    pdf = render_report_pdf(report)
    filename = f"aegis-{report.kind.value}-{report.created_at.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
