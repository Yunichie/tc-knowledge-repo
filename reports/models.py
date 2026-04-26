import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from resources.models import Resource
from users.models import User


class ReportReason(models.TextChoices):
    COPYRIGHT = "COPYRIGHT", _("Copyright Violation")
    INAPPROPRIATE = "INAPPROPRIATE", _("Inappropriate Content")
    SPAM = "SPAM", _("Spam or Misleading")
    DUPLICATE = "DUPLICATE", _("Duplicate Resource")
    OTHER = "OTHER", _("Other")


class ReportStatus(models.TextChoices):
    OPEN = "OPEN", _("Open")
    DISMISSED = "DISMISSED", _("Dismissed")
    REMOVED = "REMOVED", _("Removed")


class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="reports"
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reports_created"
    )
    reason = models.CharField(max_length=20, choices=ReportReason.choices)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.OPEN
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reports_resolved",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["resource"]),
            models.Index(fields=["reporter"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Report {self.id} - {self.reason} ({self.status})"
