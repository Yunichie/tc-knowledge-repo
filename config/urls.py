"""
The Django Ninja API is mounted at /api/.
The Django admin is available at /admin/ (for moderation convenience).
"""

from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from reports.api import router as reports_router
from resources.api import router as resources_router
from users.api import router as users_router

api = NinjaAPI(
    title="TC Knowledge Repo API",
    version="0.1.0",
    description="Backend API for the college department knowledge-sharing platform.",
)


@api.get("/health", tags=["system"])
def health_check(request):
    """returns 200 if the API is running."""
    return {"status": "ok", "version": "0.1.0"}


api.add_router("/auth/", users_router, tags=["authentication"])
api.add_router("/resources/", resources_router, tags=["resources"])
api.add_router("/reports/", reports_router, tags=["reports"])

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
