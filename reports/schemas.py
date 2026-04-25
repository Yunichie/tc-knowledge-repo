from datetime import datetime
from typing import Optional
from uuid import UUID

from ninja import Schema


class ReportIn(Schema):
    resource_id: UUID
    reason: str
    description: str


class ReportOut(Schema):
    id: UUID
    resource_id: UUID
    reporter_id: UUID
    reason: str
    description: str
    status: str
    resolved_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class ResolveReportIn(Schema):
    action: str
