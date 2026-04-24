from datetime import datetime
from typing import List, Optional
from uuid import UUID

from ninja import Field, Schema
from pydantic import model_validator


class CategoryOut(Schema):
    id: UUID
    name: str
    slug: str
    description: str


class TagOut(Schema):
    id: UUID
    name: str


class ResourceIn(Schema):
    title: str
    description: str
    type: str
    category_id: UUID
    tag_ids: List[UUID] = []

    # Optional fields based on type
    r2_object_key: Optional[str] = None
    youtube_url: Optional[str] = None
    markdown_body: Optional[str] = None


class ResourceOut(Schema):
    id: UUID
    title: str
    description: str
    type: str
    status: str
    rejection_reason: str

    r2_object_key: str
    youtube_url: str
    markdown_body: str

    category: CategoryOut
    tags: List[TagOut]
    uploader_id: UUID

    created_at: datetime
    updated_at: datetime


class ResourceFilterParams(Schema):
    category_id: Optional[UUID] = None
    tag_ids: Optional[List[UUID]] = None
    search: Optional[str] = None
    type: Optional[str] = None
    sort: Optional[str] = "newest"  # newest, oldest
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class PresignedUploadIn(Schema):
    filename: str
    content_type: str


class PresignedUploadOut(Schema):
    url: str
    fields: dict
    object_key: str


class ModerateIn(Schema):
    action: str  # approve or reject
    reason: Optional[str] = None

    @model_validator(mode="after")
    def check_reason_if_rejected(self):
        if self.action == "reject" and not self.reason:
            raise ValueError("Rejection reason is required.")
        return self


class BulkDownloadIn(Schema):
    category_id: Optional[UUID] = None
    tag_ids: Optional[List[UUID]] = None
    search: Optional[str] = None


class BulkDownloadOut(Schema):
    id: UUID
    task_id: Optional[str] = None
    status: str
    download_url: str
