from django.contrib import admin
from requests.models import ResourceRequest


@admin.register(ResourceRequest)
class ResourceRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "requester", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "description", "requester__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
