from typing import List, Optional
from uuid import UUID

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F
from ninja import Query, Router

from resources.models import (
    BulkDownload,
    Category,
    Resource,
    ResourceStatus,
    ResourceType,
    Tag,
)
from resources.schemas import (
    BulkDownloadIn,
    BulkDownloadOut,
    CategoryOut,
    ModerateIn,
    PresignedUploadIn,
    PresignedUploadOut,
    ResourceFilterParams,
    ResourceIn,
    ResourceOut,
    TagOut,
)
from resources.services import generate_presigned_put
from resources.tasks import generate_bulk_download_zip
from users.auth import authenticate_request
from users.models import UserRole

router = Router()


# Public Endpoints


@router.get("/", response=List[ResourceOut])
def list_resources(request, filters: ResourceFilterParams = Query(...)):
    """List approved resources with optional filtering, search, and pagination."""
    qs = Resource.objects.filter(status=ResourceStatus.APPROVED).select_related("category").prefetch_related("tags")

    if filters.category_id:
        qs = qs.filter(category_id=filters.category_id)

    if filters.tag_ids:
        qs = qs.filter(tags__id__in=filters.tag_ids).distinct()

    if filters.type:
        qs = qs.filter(type=filters.type)

    if filters.search:
        query = SearchQuery(filters.search)
        qs = qs.filter(search_vector=query).annotate(rank=SearchRank(F("search_vector"), query))

    if filters.search:
        qs = qs.order_by("-rank")
    elif filters.sort == "oldest":
        qs = qs.order_by("created_at")
    else:
        qs = qs.order_by("-created_at")

    return qs[filters.offset : filters.offset + filters.limit]


@router.get("/{resource_id}/", response={200: ResourceOut, 404: dict})
def get_resource(request, resource_id: UUID):
    """Get a single resource by ID."""
    try:
        resource = (
            Resource.objects.select_related("category")
            .prefetch_related("tags")
            .get(id=resource_id)
        )
        return 200, resource
    except Resource.DoesNotExist:
        return 404, {"detail": "Resource not found."}


@router.get("/categories/", response=List[CategoryOut])
def list_categories(request):
    """List all categories."""
    return Category.objects.all().order_by("name")


@router.get("/tags/", response=List[TagOut])
def list_tags(request):
    """List all tags."""
    return Tag.objects.all().order_by("name")


