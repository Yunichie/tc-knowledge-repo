"""
The Django Ninja API is mounted at /api/.
The Django admin is available at /admin/ (for moderation convenience).
"""

from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

api = NinjaAPI(
    title="TC Knowledge Repo API",
    version="0.1.0",
    description="Backend API for the college department knowledge-sharing platform.",
)


@api.get("/health", tags=["system"])
def health_check(request):
    """returns 200 if the API is running."""
    return {"status": "ok", "version": "0.1.0"}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
