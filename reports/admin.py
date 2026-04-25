from django.contrib import admin

from reports.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "resource", "reporter", "reason", "status", "resolved_by", "created_at")
    list_filter = ("reason", "status", "created_at")
    search_fields = ("description", "resource__title", "reporter__email")
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        (None, {"fields": ("resource", "reporter", "reason", "description")}),
        ("Status", {"fields": ("status", "resolved_by")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
