import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import ReportKind


class ReportSection(BaseModel):
    heading: str
    body: str = ""
    # Optional tabular data: header row + data rows
    columns: list[str] | None = None
    rows: list[list[str]] | None = None


class ReportContent(BaseModel):
    summary: str
    sections: list[ReportSection]


class ReportGenerate(BaseModel):
    kind: ReportKind
    # Required when kind == incident: the incident to report on
    subject_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ReportKind
    title: str
    subject_id: uuid.UUID | None
    provider: str
    generated_by: uuid.UUID | None
    created_at: datetime


class ReportDetail(ReportRead):
    content: ReportContent
