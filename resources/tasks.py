import os
import tempfile
import zipfile
from typing import Any, Dict

from celery import shared_task
from django.conf import settings

from resources.models import BulkDownload, BulkDownloadStatus, Resource, ResourceStatus, ResourceType
from resources.services import generate_presigned_get, get_r2_client, stream_object


@shared_task(bind=True, name="resources.tasks.generate_bulk_download_zip")
def generate_bulk_download_zip(self, bulk_download_id: str):
    """
    Background task to generate a zip file of PDFs matching the given filters.
    """
    try:
        bulk_download = BulkDownload.objects.get(id=bulk_download_id)
    except BulkDownload.DoesNotExist:
        return f"BulkDownload {bulk_download_id} not found."

    bulk_download.status = BulkDownloadStatus.PROCESSING
    bulk_download.task_id = self.request.id
    bulk_download.save()

    try:
        filters: Dict[str, Any] = bulk_download.filters
        qs = Resource.objects.filter(status=ResourceStatus.APPROVED, type=ResourceType.PDF)

        category_id = filters.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)

        tag_ids = filters.get("tag_ids")
        if tag_ids:
            qs = qs.filter(tags__id__in=tag_ids).distinct()

        search_query = filters.get("search")
        if search_query:
            qs = qs.filter(search_vector=search_query)

        resources = qs.order_by("-created_at")[:100]

        if not resources.exists():
            bulk_download.status = BulkDownloadStatus.DONE
            bulk_download.save()
            return "No PDF resources found matching filters."

        client = get_r2_client()
        zip_filename = f"bulk-downloads/{bulk_download_id}.zip"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
                # For each PDF, stream chunks from R2 into the zip
                for resource in resources:
                    if not resource.r2_object_key:
                        continue

                    ext = (
                        resource.r2_object_key.split(".")[-1]
                        if "." in resource.r2_object_key
                        else "pdf"
                    )
                    safe_title = "".join(c if c.isalnum() else "_" for c in resource.title)
                    entry_name = f"{safe_title}_{resource.id}.{ext}"

                    try:
                        with zf.open(entry_name, "w") as zf_entry:
                            for chunk in stream_object(resource.r2_object_key):
                                zf_entry.write(chunk)
                    except Exception:
                        continue

            with open(tmp_path, "rb") as f:
                client.upload_fileobj(
                    f,
                    settings.R2_BUCKET_NAME,
                    zip_filename,
                    ExtraArgs={"ContentType": "application/zip"},
                )

        os.remove(tmp_path)

        url = generate_presigned_get(zip_filename, expires_in=3600)

        bulk_download.status = BulkDownloadStatus.DONE
        bulk_download.download_url = url
        bulk_download.save()

        return f"Success: {zip_filename}"

    except Exception as e:
        bulk_download.status = BulkDownloadStatus.FAILED
        bulk_download.save()
        raise e
