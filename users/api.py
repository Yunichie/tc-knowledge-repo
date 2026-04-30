from django.db import IntegrityError
from django.utils import timezone
from ninja import Router

from .auth import authenticate_request, generate_jwt
from .models import User, UserRole
from .schemas import AuthResponseSchema, GoogleAuthSchema, LoginSchema, RegisterSchema, UserSchema

router = Router()


@router.post("/register/", response={201: AuthResponseSchema, 400: dict})
def register(request, data: RegisterSchema):
    try:
        user = User.objects.create_user(
            email=data.email,
            password=data.password,
            first_name=data.first_name or "",
            last_name=data.last_name or "",
            role=UserRole.STUDENT,
        )

        access_token = generate_jwt(user)

        return 201, {
            "access_token": access_token,
            "user": user,
        }
    except IntegrityError:
        return 400, {"detail": "Email already registered"}
    except ValueError as e:
        return 400, {"detail": str(e)}


@router.post("/login/", response={200: AuthResponseSchema, 401: dict, 403: dict})
def login(request, data: LoginSchema):
    try:
        user = User.objects.get(email=data.email)
    except User.DoesNotExist:
        return 401, {"detail": "Invalid credentials"}

    if not user.check_password(data.password):
        return 401, {"detail": "Invalid credentials"}

    if not user.is_active:
        return 403, {"detail": "Account is inactive"}

    if user.banned_until and user.banned_until > timezone.now():
        ban_date = user.banned_until.strftime("%Y-%m-%d %H:%M:%S")
        return 403, {"detail": f"Your account is temporarily suspended until {ban_date} UTC."}

    access_token = generate_jwt(user)

    return 200, {
        "access_token": access_token,
        "user": user,
    }


@router.post("/google/", response={200: AuthResponseSchema, 401: dict})
def google_auth(request, data: GoogleAuthSchema):
    # Google OAuth temporarily disabled due to naming conflict with requests Django app
    # TODO: Re-enable after resolving import conflict
    return 401, {"detail": "Google OAuth temporarily unavailable"}


@router.get("/me/", response={200: UserSchema, 401: dict})
def get_profile(request):
    try:
        user = authenticate_request(request)
        return 200, user
    except ValueError as e:
        return 401, {"detail": str(e)}
