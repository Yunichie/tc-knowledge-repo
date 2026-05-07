import contextlib
from uuid import UUID

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import models
from django.db.models import Count, F
from ninja import Query, Router

from reports.models import Report, ReportStatus
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
from resources.services import delete_r2_object, generate_presigned_put
from resources.tasks import generate_bulk_download_zip, process_resource_moderation
from users.auth import authenticate_request
from users.models import UserRole

router = Router()


# Public Endpoints


@router.get("/", response={200: list[ResourceOut], 401: dict, 403: dict})
def list_resources(request, filters: ResourceFilterParams = Query(...)):
    """List resources. Defaults to APPROVED. Admins can filter by other statuses."""
    if filters.status and filters.status != ResourceStatus.APPROVED:
        try:
            user = authenticate_request(request)
        except ValueError as e:
            return 401, {"detail": str(e)}

        if user.role != UserRole.ADMIN:
            return 403, {"detail": "Admin access required to view non-approved resources."}

        qs = Resource.objects.filter(status=filters.status)
    else:
        qs = Resource.objects.filter(status=ResourceStatus.APPROVED)

    qs = qs.select_related("category", "uploader").prefetch_related("tags")

    if filters.category_id:
        qs = qs.filter(category_id=filters.category_id)

    if filters.tag_ids:
        qs = qs.filter(tags__id__in=filters.tag_ids).distinct()

    if filters.type:
        qs = qs.filter(type=filters.type)

    if filters.search:
        query = SearchQuery(filters.search, config="english")
        qs = qs.filter(search_vector=query).annotate(rank=SearchRank(F("search_vector"), query))

    if filters.search:
        qs = qs.order_by("-rank")
    elif filters.sort == "oldest":
        qs = qs.order_by("created_at")
    else:
        qs = qs.order_by("-created_at")

    return 200, list(qs[filters.offset : filters.offset + filters.limit])


@router.get("/{uuid:resource_id}/", response={200: ResourceOut, 404: dict})
def get_resource(request, resource_id: UUID):
    """Get a single resource by ID."""
    try:
        resource = Resource.objects.select_related("category", "uploader").prefetch_related("tags").get(id=resource_id)
        return 200, resource
    except Resource.DoesNotExist:
        return 404, {"detail": "Resource not found."}


@router.get("/{uuid:resource_id}/related/", response={200: list[ResourceOut], 404: dict})
def get_related_resources(request, resource_id: UUID):
    """Returns related resources based on same category and overlapping tags."""
    try:
        resource = Resource.objects.prefetch_related("tags").get(id=resource_id)
    except Resource.DoesNotExist:
        return 404, {"detail": "Resource not found."}

    tag_ids = list(resource.tags.values_list("id", flat=True))

    qs = (
        Resource.objects.filter(
            category_id=resource.category_id,
            status=ResourceStatus.APPROVED,
        )
        .exclude(id=resource_id)
        .select_related("category", "uploader")
        .prefetch_related("tags")
    )

    if tag_ids:
        qs = (
            qs.filter(tags__id__in=tag_ids)
            .annotate(shared_tag_count=Count("tags", filter=models.Q(tags__id__in=tag_ids)))
            .order_by("-shared_tag_count", "-created_at")
        )
    else:
        qs = qs.order_by("-created_at")

    return 200, list(qs.distinct()[:10])


@router.get("/categories/", response=list[CategoryOut])
def list_categories(request):
    """List all categories."""
    return Category.objects.all().order_by("name")


@router.get("/tags/", response=list[TagOut])
def list_tags(request):
    """List all tags."""
    return Tag.objects.all().order_by("name")


# Student endpoints


@router.post("/", response={201: ResourceOut, 400: dict, 401: dict})
def create_resource(request, data: ResourceIn):
    """Submit a new resource (status defaults to PENDING)."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    # Validate type-specific fields
    if data.type == ResourceType.PDF and not data.r2_object_key:
        return 400, {"detail": "r2_object_key is required for PDF resources."}
    if data.type == ResourceType.YOUTUBE and not data.youtube_url:
        return 400, {"detail": "youtube_url is required for YouTube resources."}
    if data.type == ResourceType.MARKDOWN and not data.markdown_body:
        return 400, {"detail": "markdown_body is required for Markdown resources."}

    try:
        Category.objects.get(id=data.category_id)
    except Category.DoesNotExist:
        return 400, {"detail": "Category not found."}

    resource = Resource.objects.create(
        title=data.title,
        description=data.description,
        type=data.type,
        category_id=data.category_id,
        uploader=user,
        r2_object_key=data.r2_object_key or "",
        youtube_url=data.youtube_url or "",
        markdown_body=data.markdown_body or "",
    )

    if data.tag_ids:
        tags = Tag.objects.filter(id__in=data.tag_ids)
        resource.tags.set(tags)

    resource = Resource.objects.select_related("category", "uploader").prefetch_related("tags").get(id=resource.id)

    process_resource_moderation.delay(str(resource.id))

    return 201, resource


@router.post("/presigned-upload/", response={200: PresignedUploadOut, 401: dict})
def presigned_upload(request, data: PresignedUploadIn):
    """Generate a presigned PUT URL for direct-to-R2 file upload."""
    try:
        authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    result = generate_presigned_put(data.filename, data.content_type)
    return 200, result


@router.post("/bulk-download/", response={201: BulkDownloadOut, 401: dict})
def create_bulk_download(request, data: BulkDownloadIn):
    """Enqueue a bulk download zip job and return its tracking ID."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    filters = {}
    if data.category_id:
        filters["category_id"] = str(data.category_id)
    if data.tag_ids:
        filters["tag_ids"] = [str(tid) for tid in data.tag_ids]
    if data.search:
        filters["search"] = data.search

    bulk_download = BulkDownload.objects.create(student=user, filters=filters)

    task = generate_bulk_download_zip.delay(str(bulk_download.id))

    bulk_download.task_id = task.id
    bulk_download.save()

    return 201, bulk_download


@router.get("/bulk-download/{bulk_download_id}/", response={200: BulkDownloadOut, 401: dict, 404: dict})
def get_bulk_download(request, bulk_download_id: UUID):
    """Poll the status of a bulk download job."""
    try:
        authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    try:
        bulk_download = BulkDownload.objects.get(id=bulk_download_id)
        return 200, bulk_download
    except BulkDownload.DoesNotExist:
        return 404, {"detail": "Bulk download not found."}


# Admin Endpoints


@router.patch("/{resource_id}/moderate/", response={200: ResourceOut, 400: dict, 401: dict, 403: dict, 404: dict})
def moderate_resource(request, resource_id: UUID, data: ModerateIn):
    """Approve or reject a pending resource"""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    if user.role != UserRole.ADMIN:
        return 403, {"detail": "Admin access required."}

    try:
        resource = Resource.objects.select_related("category", "uploader").prefetch_related("tags").get(id=resource_id)
    except Resource.DoesNotExist:
        return 404, {"detail": "Resource not found."}

    if data.action == "approve":
        resource.status = ResourceStatus.APPROVED
        resource.rejection_reason = ""
    elif data.action == "reject":
        resource.status = ResourceStatus.REJECTED
        resource.rejection_reason = data.reason or ""
    else:
        return 400, {"detail": "Action must be 'approve' or 'reject'."}

    resource.save()
    return 200, resource


@router.delete("/{uuid:resource_id}/", response={204: None, 401: dict, 403: dict, 404: dict})
def delete_resource(request, resource_id: UUID):
    """Delete a resource. Students can delete their own; admins can delete only reported+rejected resources."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        return 404, {"detail": "Resource not found."}

    is_owner = resource.uploader_id == user.id
    is_admin = user.role == UserRole.ADMIN

    if not is_owner and not is_admin:
        return 403, {"detail": "You do not have permission to delete this resource."}

    if is_admin and not is_owner:
        has_open_report = Report.objects.filter(resource=resource, status=ReportStatus.OPEN).exists()
        if not has_open_report or resource.status != ResourceStatus.REJECTED:
            return 403, {"detail": "Admins can only delete resources that are rejected and have an open report."}

    if resource.type == ResourceType.PDF and resource.r2_object_key:
        with contextlib.suppress(Exception):
            delete_r2_object(resource.r2_object_key)

    resource.delete()
    return 204, None
