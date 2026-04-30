import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from resources.models import Resource
from users.models import User


class ResourceRequestStatus(models.TextChoices):
    OPEN = "OPEN", _("Open")
    FULFILLED = "FULFILLED", _("Fulfilled")


class ResourceRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ResourceRequestStatus.choices,
        default=ResourceRequestStatus.OPEN,
    )

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="resource_requests")
    fulfilled_by_resource = models.ForeignKey(
        Resource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfills_request",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resource_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
