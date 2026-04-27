from uuid import UUID

from ninja import Router

from requests.models import ResourceRequest, ResourceRequestStatus
from requests.schemas import (
    ResourceRequestCreateSchema,
    ResourceRequestDetailSchema,
    ResourceRequestFulfillSchema,
    ResourceRequestListSchema,
)
from resources.models import Resource
from users.auth import authenticate_request

router = Router()


@router.get("/", response=list[ResourceRequestListSchema])
def list_requests(request):
    """List open resource requests."""
    requests_qs = ResourceRequest.objects.filter(
        status=ResourceRequestStatus.OPEN
    ).order_by("-created_at")
    return requests_qs


@router.post("/", response={201: ResourceRequestDetailSchema, 401: dict})
def create_request(request, data: ResourceRequestCreateSchema):
    """Create a new resource request (student only)."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    new_request = ResourceRequest.objects.create(
        title=data.title,
        description=data.description,
        requester=user,
    )
    return 201, new_request


@router.get("/{request_id}/", response={200: ResourceRequestDetailSchema, 404: dict})
def get_request(request, request_id: UUID):
    """Get a single resource request by ID."""
    try:
        resource_request = ResourceRequest.objects.get(id=request_id)
        return 200, resource_request
    except ResourceRequest.DoesNotExist:
        return 404, {"detail": "Request not found."}


@router.patch(
    "/{request_id}/fulfill/",
    response={200: ResourceRequestDetailSchema, 400: dict, 401: dict, 404: dict},
)
def fulfill_request(request, request_id: UUID, data: ResourceRequestFulfillSchema):
    """Fulfill a request by linking a resource (student only)."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    try:
        resource_request = ResourceRequest.objects.get(id=request_id)
    except ResourceRequest.DoesNotExist:
        return 404, {"detail": "Request not found."}

    if resource_request.status != ResourceRequestStatus.OPEN:
        return 400, {"detail": "Request is not open for fulfillment."}

    try:
        resource = Resource.objects.get(id=data.resource_id)
    except Resource.DoesNotExist:
        return 400, {"detail": "Resource not found."}

    resource_request.fulfilled_by_resource = resource
    resource_request.status = ResourceRequestStatus.FULFILLED
    resource_request.save()

    return 200, resource_request
