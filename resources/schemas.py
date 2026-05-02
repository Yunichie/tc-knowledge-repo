from datetime import datetime
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
    type: str


class ResourceIn(Schema):
    title: str
    description: str
    type: str
    category_id: UUID
    tag_ids: list[UUID] = []

    # Optional fields based on type
    r2_object_key: str | None = None
    youtube_url: str | None = None
    markdown_body: str | None = None


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
    tags: list[TagOut]
    uploader_id: UUID

    created_at: datetime
    updated_at: datetime


class ResourceFilterParams(Schema):
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    search: str | None = None
    type: str | None = None
    status: str | None = None
    sort: str | None = "newest"  # newest, oldest
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class PresignedUploadIn(Schema):
    filename: str
    content_type: str


class PresignedUploadOut(Schema):
    url: str
    object_key: str


class ModerateIn(Schema):
    action: str  # approve or reject
    reason: str | None = None

    @model_validator(mode="after")
    def check_reason_if_rejected(self):
        if self.action == "reject" and not self.reason:
            raise ValueError("Rejection reason is required.")
        return self


class BulkDownloadIn(Schema):
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    search: str | None = None


class BulkDownloadOut(Schema):
    id: UUID
    task_id: str | None = None
    status: str
    download_url: str
