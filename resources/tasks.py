import os
import tempfile
import zipfile
from typing import Any

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
        filters: dict[str, Any] = bulk_download.filters
        qs = Resource.objects.filter(status=ResourceStatus.APPROVED, type=ResourceType.PDF)

        category_id = filters.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)

        tag_ids = filters.get("tag_ids")
        if tag_ids:
            qs = qs.filter(tags__id__in=tag_ids).distinct()

        search_query = filters.get("search")
        if search_query:
            from django.contrib.postgres.search import SearchQuery
            qs = qs.filter(search_vector=SearchQuery(search_query, config="english"))

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

                    ext = resource.r2_object_key.split(".")[-1] if "." in resource.r2_object_key else "pdf"
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


SPAM_KEYWORDS = [
    # add keywords later
]

MINHASH_NUM_PERM = 128
MINHASH_THRESHOLD = 0.9


def _check_magic_bytes(resource):
    """Verify PDF files start with %PDF- header."""
    if resource.type != ResourceType.PDF or not resource.r2_object_key:
        return True, ""
    try:
        header = b""
        for chunk in stream_object(resource.r2_object_key):
            header += chunk
            if len(header) >= 5:
                break
        if not header[:5].startswith(b"%PDF-"):
            return False, "File integrity check failed."
    except Exception:
        return False, "File integrity check failed."
    return True, ""


def _check_spam_keywords(resource):
    """Scan title and description for spam keywords."""
    text = f"{resource.title} {resource.description}".lower()
    for keyword in SPAM_KEYWORDS:
        if keyword in text:
            return False, "Content flagged for spam."
    return True, ""


def _compute_file_hash(resource):
    """Compute SHA-256 of the file content and check for exact duplicates."""
    import hashlib

    if resource.type == ResourceType.PDF and resource.r2_object_key:
        sha256 = hashlib.sha256()
        try:
            for chunk in stream_object(resource.r2_object_key):
                sha256.update(chunk)
        except Exception:
            return True, "", ""
        return True, "", sha256.hexdigest()
    elif resource.type == ResourceType.MARKDOWN and resource.markdown_body:
        return True, "", hashlib.sha256(resource.markdown_body.encode()).hexdigest()
    return True, "", ""


def _check_exact_duplicate(resource, file_hash):
    """Check if the computed hash matches any existing resource."""
    if not file_hash:
        return True, ""
    duplicate = (
        Resource.objects.filter(file_hash=file_hash, status=ResourceStatus.APPROVED).exclude(id=resource.id).first()
    )
    if duplicate:
        return False, "Exact duplicate detected."
    return True, ""


def _compute_minhash(text):
    """Compute a MinHash signature from text."""
    from datasketch import MinHash

    mh = MinHash(num_perm=MINHASH_NUM_PERM)
    for word in text.lower().split():
        mh.update(word.encode("utf-8"))
    return mh


def _extract_pdf_text(resource):
    """Extract text from a PDF stored in R2."""
    import io

    from pypdf import PdfReader

    if not resource.r2_object_key:
        return ""
    try:
        data = b""
        for chunk in stream_object(resource.r2_object_key):
            data += chunk
        reader = PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
        return text.strip()
    except Exception:
        return ""


def _check_near_duplicate(resource, text):
    """Check MinHash similarity against existing approved resources."""
    from datasketch import MinHash

    if not text or len(text.split()) < 10:
        return True, "", None

    mh = _compute_minhash(text)
    signature = mh.hashvalues.tolist()

    similar_resources = (
        Resource.objects.filter(
            status=ResourceStatus.APPROVED,
            minhash_signature__isnull=False,
        )
        .exclude(id=resource.id)
        .values_list("minhash_signature", flat=True)
    )

    for stored_sig in similar_resources:
        other_mh = MinHash(num_perm=MINHASH_NUM_PERM)
        other_mh.hashvalues = __import__("numpy").array(stored_sig, dtype="uint64")
        similarity = mh.jaccard(other_mh)
        if similarity > MINHASH_THRESHOLD:
            pct = int(similarity * 100)
            return False, f"Near-duplicate content detected ({pct}% similarity).", signature

    return True, "", signature


def _increment_user_strike(user):
    """Increment user strike count and apply temp ban if threshold reached."""
    from datetime import timedelta

    from django.utils import timezone

    user.strike_count += 1
    if user.strike_count >= 3:
        user.banned_until = timezone.now() + timedelta(days=7)
    user.save()


@shared_task(bind=True, name="resources.tasks.process_resource_moderation")
def process_resource_moderation(self, resource_id: str):
    """Auto-moderation pipeline: magic bytes, spam, exact hash, near-duplicate."""
    try:
        resource = Resource.objects.select_related("uploader").get(id=resource_id)
    except Resource.DoesNotExist:
        return f"Resource {resource_id} not found."

    if resource.status != ResourceStatus.PENDING:
        return f"Resource {resource_id} is not PENDING, skipping."

    # 1. Magic bytes check (PDF only)
    passed, reason = _check_magic_bytes(resource)
    if not passed:
        resource.status = ResourceStatus.REJECTED
        resource.rejection_reason = reason
        resource.save()
        return f"REJECTED: {reason}"

    # 2. Spam keyword check
    passed, reason = _check_spam_keywords(resource)
    if not passed:
        resource.status = ResourceStatus.REJECTED
        resource.rejection_reason = reason
        resource.save()
        return f"REJECTED: {reason}"

    # 3. Exact hash check
    _, _, file_hash = _compute_file_hash(resource)
    if file_hash:
        resource.file_hash = file_hash

    passed, reason = _check_exact_duplicate(resource, file_hash)
    if not passed:
        resource.status = ResourceStatus.REJECTED
        resource.rejection_reason = reason
        resource.save()
        _increment_user_strike(resource.uploader)
        return f"REJECTED: {reason}"

    # 4. Near-duplicate check (PDF and Markdown only, skip YouTube)
    if resource.type == ResourceType.PDF:
        text = _extract_pdf_text(resource)
    elif resource.type == ResourceType.MARKDOWN:
        text = resource.markdown_body or ""
    else:
        text = ""

    if text:
        passed, reason, signature = _check_near_duplicate(resource, text)
        if signature:
            resource.minhash_signature = signature
        if not passed:
            resource.status = ResourceStatus.REJECTED
            resource.rejection_reason = reason
            resource.save()
            return f"REJECTED: {reason}"

    # 5. All checks passed
    resource.status = ResourceStatus.APPROVED
    resource.save()
    return f"APPROVED: {resource_id}"
