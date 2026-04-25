from django.contrib import admin

from resources.models import BulkDownload, Category, Resource, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "status", "category", "uploader", "created_at")
    list_filter = ("status", "type", "category")
    search_fields = ("title", "description")
    readonly_fields = ("id", "search_vector", "created_at", "updated_at")


@admin.register(BulkDownload)
class BulkDownloadAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("id", "task_id", "filters", "created_at", "updated_at")
