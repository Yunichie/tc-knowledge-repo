from datetime import datetime
from uuid import UUID

from django.conf import settings
from pydantic import BaseModel, EmailStr, field_validator


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v):
        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", ["student.its.ac.id", "its.ac.id"])
        domain = v.split("@")[1] if "@" in v else ""
        if domain not in allowed_domains:
            raise ValueError("Registration is restricted to institutional email addresses.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthSchema(BaseModel):
    id_token: str


class UserSchema(BaseModel):
    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    banned_until: datetime | None = None
    date_joined: datetime

    class Config:
        from_attributes = True


class AuthResponseSchema(BaseModel):
    access_token: str
    user: UserSchema
