import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from requests.models import ResourceRequest, ResourceRequestStatus
from resources.models import Category, Resource, ResourceStatus, ResourceType
from users.models import UserRole

User = get_user_model()


class ResourceRequestModelTest(TestCase):
    """Test ResourceRequest model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def test_create_resource_request(self):
        """Test creating a resource request."""
        req = ResourceRequest.objects.create(
            title="Looking for Calculus Notes",
            description="Need calculus notes from last semester",
            requester=self.user,
        )
        self.assertEqual(req.status, ResourceRequestStatus.OPEN)
        self.assertEqual(req.requester, self.user)
        self.assertIsNone(req.fulfilled_by_resource)

    def test_resource_request_str(self):
        """Test string representation of resource request."""
        req = ResourceRequest.objects.create(
            title="Test Request",
            description="Test description",
            requester=self.user,
        )
        self.assertEqual(str(req), "Test Request")


class ResourceRequestAPITest(TestCase):
    """Test ResourceRequest API endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="student@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            role=UserRole.STUDENT,
        )
        self.category = Category.objects.create(
            name="Mathematics",
            slug="mathematics",
        )
        self.resource = Resource.objects.create(
            title="Calculus Notes",
            description="Complete calculus notes",
            type=ResourceType.PDF,
            category=self.category,
            uploader=self.user,
            status=ResourceStatus.APPROVED,
            r2_object_key="test.pdf",
        )

    def test_list_requests_anonymous(self):
        """Test listing requests as anonymous user."""
        ResourceRequest.objects.create(
            title="Looking for Physics Notes",
            description="Need physics notes",
            requester=self.user,
        )
        response = self.client.get("/api/requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_create_request_requires_auth(self):
        """Test that creating a request requires authentication."""
        response = self.client.post(
            "/api/requests/",
            data=json.dumps({
                "title": "Looking for Notes",
                "description": "Need some notes",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_create_request_with_auth(self):
        """Test creating a request with authentication."""
        response = self.client.post(
            "/api/requests/",
            data=json.dumps({
                "title": "Looking for Discrete Math",
                "description": "Need discrete mathematics textbook",
            }),
            content_type="application/json",
            HTTP_X_USER_ID=str(self.user.id),
            HTTP_X_USER_ROLE=UserRole.STUDENT,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["title"], "Looking for Discrete Math")
        self.assertEqual(data["status"], ResourceRequestStatus.OPEN)

    def test_get_request_detail(self):
        """Test getting a single request detail."""
        req = ResourceRequest.objects.create(
            title="Looking for Notes",
            description="Test description",
            requester=self.user,
        )
        response = self.client.get(f"/api/requests/{req.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], str(req.id))
        self.assertEqual(data["title"], "Looking for Notes")

    def test_get_nonexistent_request(self):
        """Test getting a nonexistent request returns 404."""
        fake_id = uuid4()
        response = self.client.get(f"/api/requests/{fake_id}/")
        self.assertEqual(response.status_code, 404)

    def test_fulfill_request_requires_auth(self):
        """Test that fulfilling a request requires authentication."""
        req = ResourceRequest.objects.create(
            title="Looking for Notes",
            description="Test description",
            requester=self.user,
        )
        response = self.client.patch(
            f"/api/requests/{req.id}/fulfill/",
            data=json.dumps({
                "resource_id": str(self.resource.id),
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_fulfill_request_with_auth(self):
        """Test fulfilling a request with authentication."""
        req = ResourceRequest.objects.create(
            title="Looking for Calculus",
            description="Need calculus notes",
            requester=self.user,
        )
        response = self.client.patch(
            f"/api/requests/{req.id}/fulfill/",
            data=json.dumps({
                "resource_id": str(self.resource.id),
            }),
            content_type="application/json",
            HTTP_X_USER_ID=str(self.user.id),
            HTTP_X_USER_ROLE=UserRole.STUDENT,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], ResourceRequestStatus.FULFILLED)
        self.assertEqual(data["fulfilled_by_resource_id"], str(self.resource.id))

    def test_fulfill_already_fulfilled_request(self):
        """Test fulfilling an already fulfilled request fails."""
        req = ResourceRequest.objects.create(
            title="Looking for Notes",
            description="Test description",
            requester=self.user,
            status=ResourceRequestStatus.FULFILLED,
            fulfilled_by_resource=self.resource,
        )
        response = self.client.patch(
            f"/api/requests/{req.id}/fulfill/",
            data=json.dumps({
                "resource_id": str(self.resource.id),
            }),
            content_type="application/json",
            HTTP_X_USER_ID=str(self.user.id),
            HTTP_X_USER_ROLE=UserRole.STUDENT,
        )
        self.assertEqual(response.status_code, 400)

    def test_fulfill_with_nonexistent_resource(self):
        """Test fulfilling with a nonexistent resource returns 400."""
        req = ResourceRequest.objects.create(
            title="Looking for Notes",
            description="Test description",
            requester=self.user,
        )
        fake_resource_id = uuid4()
        response = self.client.patch(
            f"/api/requests/{req.id}/fulfill/",
            data=json.dumps({
                "resource_id": str(fake_resource_id),
            }),
            content_type="application/json",
            HTTP_X_USER_ID=str(self.user.id),
            HTTP_X_USER_ROLE=UserRole.STUDENT,
        )
        self.assertEqual(response.status_code, 400)
