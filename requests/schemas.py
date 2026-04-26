from datetime import datetime
from uuid import UUID

from ninja import Schema


class ResourceRequestCreateSchema(Schema):
    title: str
    description: str


class ResourceRequestDetailSchema(Schema):
    id: UUID
    title: str
    description: str
    status: str
    requester_id: UUID
    fulfilled_by_resource_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ResourceRequestListSchema(Schema):
    id: UUID
    title: str
    description: str
    status: str
    requester_id: UUID
    fulfilled_by_resource_id: UUID | None
    created_at: datetime


class ResourceRequestFulfillSchema(Schema):
    resource_id: UUID
