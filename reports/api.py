from uuid import UUID

from ninja import Router

from reports.models import Report, ReportStatus
from reports.schemas import ReportIn, ReportOut, ResolveReportIn
from resources.models import Resource, ResourceStatus
from users.auth import authenticate_request
from users.models import UserRole

router = Router()


@router.post("/", response={201: ReportOut, 400: dict, 401: dict})
def create_report(request, data: ReportIn):
    """Submit a report for a resource."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    try:
        resource = Resource.objects.get(id=data.resource_id)
    except Resource.DoesNotExist:
        return 400, {"detail": "Resource not found."}

    report = Report.objects.create(
        resource=resource,
        reporter=user,
        reason=data.reason,
        description=data.description,
    )

    distinct_reporters = (
        Report.objects.filter(resource=resource, status=ReportStatus.OPEN).values("reporter_id").distinct().count()
    )
    if distinct_reporters >= 3 and resource.status == ResourceStatus.APPROVED:
        resource.status = ResourceStatus.QUARANTINED
        resource.save()

    return 201, report


@router.get("/", response={200: list[ReportOut], 401: dict, 403: dict})
def list_reports(request):
    """List all reports (admin only)."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    if user.role != UserRole.ADMIN:
        return 403, {"detail": "Admin access required."}

    reports = Report.objects.all().order_by("-created_at")
    return 200, list(reports)


@router.patch("/{report_id}/resolve/", response={200: ReportOut, 400: dict, 401: dict, 403: dict, 404: dict})
def resolve_report(request, report_id: UUID, data: ResolveReportIn):
    """Resolve a report by dismissing or removing the resource."""
    try:
        user = authenticate_request(request)
    except ValueError as e:
        return 401, {"detail": str(e)}

    if user.role != UserRole.ADMIN:
        return 403, {"detail": "Admin access required."}

    try:
        report = Report.objects.get(id=report_id)
    except Report.DoesNotExist:
        return 404, {"detail": "Report not found."}

    if data.action not in ["dismiss", "remove_resource"]:
        return 400, {"detail": "Action must be 'dismiss' or 'remove_resource'."}

    if data.action == "dismiss":
        report.status = ReportStatus.DISMISSED
        report.resolved_by = user
    elif data.action == "remove_resource":
        report.status = ReportStatus.REMOVED
        report.resolved_by = user

        resource = report.resource
        if resource.status == ResourceStatus.APPROVED:
            resource.status = ResourceStatus.REJECTED
            resource.save()

    report.save()
    return 200, report
