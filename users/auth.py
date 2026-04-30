from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

from .models import User


def generate_jwt(user: User) -> str:
    """Generate a JWT token for the given user."""
    expiration = datetime.utcnow() + timedelta(hours=getattr(settings, "JWT_EXPIRATION_HOURS", 24))

    payload = {
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
        "exp": expiration,
    }

    secret_key = getattr(settings, "JWT_SECRET_KEY", "dev-secret-key")
    algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")

    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token


def validate_jwt(token: str) -> dict:
    """Validate and decode a JWT token."""
    try:
        secret_key = getattr(settings, "JWT_SECRET_KEY", "dev-secret-key")
        algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")

        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Invalid or expired token")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid or expired token")


def get_user_from_token(token: str) -> User:
    """Extract user from JWT token."""
    payload = validate_jwt(token)
    user_id = payload.get("user_id")

    if not user_id:
        raise ValueError("Invalid token payload")

    try:
        user = User.objects.get(id=user_id)
        return user
    except User.DoesNotExist:
        raise ValueError("User not found")


def authenticate_request(request: HttpRequest) -> User | None:
    """
    Authenticate a request using JWT or dev headers.
    In production: extracts and validates Bearer token.
    In development: reads X-User-Id and X-User-Role headers.
    """
    dev_auth_enabled = getattr(settings, "DEV_AUTH_ENABLED", False)

    if dev_auth_enabled:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                user_role = request.headers.get("X-User-Role")
                if user_role:
                    user.role = user_role.upper()

                if user.banned_until and user.banned_until > timezone.now():
                    raise ValueError("Account temporarily suspended")

                return user
            except User.DoesNotExist:
                raise ValueError("Authentication required")

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise ValueError("Authentication required")

    if not auth_header.startswith("Bearer "):
        raise ValueError("Invalid authorization header")

    token = auth_header.split(" ")[1]
    user = get_user_from_token(token)

    if user.banned_until and user.banned_until > timezone.now():
        raise ValueError("Account temporarily suspended")

    return user
