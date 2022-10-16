import json

import posthog
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, inline_serializer
from knox.models import AuthToken
from knox.views import LoginView as KnoxLoginView
from knox.views import LogoutView as KnoxLogoutView
from metering_billing.models import Organization, OrganizationInviteToken, User
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from metering_billing.services.user import user_service
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

POSTHOG_PERSON = settings.POSTHOG_PERSON


class LoginViewMixin(KnoxLoginView):
    authentication_classes = [BasicAuthentication]
    permission_classes = [AllowAny]


class LogoutViewMixin(KnoxLogoutView):
    permission_classes = [AllowAny]


class LoginView(LoginViewMixin, APIView):
    def post(self, request, format=None):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST
            )

        if data is None:
            return JsonResponse(
                {"detail": "No data provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        username = data.get("username")
        password = data.get("password")

        if username is None or password is None:
            return JsonResponse(
                {"detail": "Please provide username and password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)

        if user is None:
            return JsonResponse(
                {"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST
            )

        login(request, user)
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else user.organization.company_name,
            event="succesful login",
        )
        token = AuthToken.objects.create(user)
        return Response(
            {
                "detail": "Successfully logged in.",
                "token": token[1],
            }
        )


class LogoutView(LogoutViewMixin):
    def post(self, request, format=None):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"detail": "You're not logged in."}, status=status.HTTP_400_BAD_REQUEST
            )
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else request.user.organization.company_name,
            event="logout",
        )
        return super(LogoutView, self).post(request, format)


class InitResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user_service.init_reset_password(email=email)

        return JsonResponse({"email": email})


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Verifies the token and resets the password."""
        user_id = request.data.get("userId", None)
        raw_password = request.data.get("password", None)
        token = request.data.get("token", None)

        if not (user_id and raw_password and token):
            raise JsonResponse(status=status.HTTP_400_BAD_REQUEST)

        user = user_service.reset_password(
            user_id=user_id, raw_password=raw_password, token=token
        )
        if user:
            login(request, user)
            return Response(
                {
                    "detail": "Successfully changed password.",
                    "token": AuthToken.objects.create(user)[1],
                }
            )

        raise PermissionDenied({"message": "This reset link is no longer valid"})


class SessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return JsonResponse({"isAuthenticated": True})


@extend_schema(
    request=RegistrationSerializer,
    responses={
        201: inline_serializer(
            "RegistrationResponse", fields={"detail": serializers.CharField()}
        )
    },
)
class RegisterView(LoginViewMixin, APIView):
    def post(self, request, format=None):
        register_data = request.data.get("register")
        invite_token = register_data.get("invite_token", None)
        serializer = RegistrationSerializer(
            data=request.data, context={"invite_token": invite_token}
        )
        serializer.is_valid(raise_exception=True)
        reg_dict = serializer.validated_data["register"]
        username = reg_dict["username"]
        email = reg_dict["email"]
        password = reg_dict["password"]
        company_name = reg_dict["company_name"]

        if invite_token is not None and invite_token != "null":
            now = datetime.datetime.now(datetime.timezone.utc)
            try:
                token = OrganizationInviteToken.objects.get(
                    token=invite_token, expire_at__gt=now
                )
            except OrganizationInviteToken.DoesNotExist:
                return Response(
                    {"detail": "Invalid invite token."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if token.email != email:
                return Response(
                    {"detail": "Email entered does not match invitation email."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            org = token.organization
        else:
            # Organization doesn't exist yet
            existing_org_num = Organization.objects.filter(
                company_name=company_name
            ).count()
            if existing_org_num > 0:
                return JsonResponse(
                    {"detail": "Organization already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            org = Organization.objects.create(
                company_name=reg_dict["company_name"],
            )
            token = None

        existing_user_num = User.objects.filter(username=username).count()
        if existing_user_num > 0:
            msg = f"User with username already exists"
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        existing_user_num = User.objects.filter(email=email).count()
        if existing_user_num > 0:
            msg = f"User with email already exists"
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            organization=org,
        )
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else org.company_name,
            event="register",
            properties={"company_name": org.company_name},
        )
        if token:
            token.delete()
        return Response(
            {
                "detail": "Successfully registered.",
                "token": AuthToken.objects.create(user)[1],
            },
            status=status.HTTP_201_CREATED,
        )
