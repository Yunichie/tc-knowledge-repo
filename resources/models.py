import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.utils.translation import gettext_lazy as _

from users.models import User


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class TagType(models.TextChoices):
    SEMESTER = "SEMESTER", _("Semester")
    TAHUN = "TAHUN", _("Tahun")
    KELAS = "KELAS", _("Kelas")
    GENERAL = "GENERAL", _("General")


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=20, choices=TagType.choices, default=TagType.GENERAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ResourceType(models.TextChoices):
    PDF = "PDF", _("PDF")
    YOUTUBE = "YOUTUBE", _("YouTube")
    MARKDOWN = "MARKDOWN", _("Markdown")


class ResourceStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")
    QUARANTINED = "QUARANTINED", _("Quarantined")


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000)
    type = models.CharField(max_length=20, choices=ResourceType.choices)
    status = models.CharField(max_length=20, choices=ResourceStatus.choices, default=ResourceStatus.PENDING)
    rejection_reason = models.TextField(blank=True)

    # Dedup fields
    file_hash = models.CharField(max_length=64, blank=True, db_index=True)
    minhash_signature = models.JSONField(null=True, blank=True)

    # Type-specific fields
    r2_object_key = models.CharField(max_length=1000, blank=True)
    youtube_url = models.URLField(blank=True)
    markdown_body = models.TextField(blank=True)

    # Relations
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="resources")
    tags = models.ManyToManyField(Tag, related_name="resources")
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploaded_resources")

    # Search
    search_vector = models.GeneratedField(
        expression=SearchVector("title", config="english", weight="A")
        + SearchVector("description", config="english", weight="B")
        + SearchVector("markdown_body", config="english", weight="C"),
        output_field=SearchVectorField(null=True, blank=True),
        db_persist=True,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"]),
        ]

    def __str__(self):
        return self.title


class BulkDownloadStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    PROCESSING = "PROCESSING", _("Processing")
    DONE = "DONE", _("Done")
    FAILED = "FAILED", _("Failed")


class BulkDownload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=BulkDownloadStatus.choices, default=BulkDownloadStatus.PENDING)
    filters = models.JSONField(default=dict)
    download_url = models.URLField(max_length=1000, blank=True)

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bulk_downloads")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BulkDownload {self.id} ({self.status})"
