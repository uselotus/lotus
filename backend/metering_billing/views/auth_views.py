import json
import logging
import time

# import lotus_python
import posthog
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from knox.models import AuthToken
from knox.views import LoginView as KnoxLoginView
from knox.views import LogoutView as KnoxLogoutView
from metering_billing.demos import setup_demo4
from metering_billing.exceptions import (
    DuplicateOrganization,
    DuplicateUser,
    InvalidRequest,
    RegistrationFailure,
)
from metering_billing.models import Organization, Team, TeamInviteToken, User
from metering_billing.serializers.auth_serializers import (
    DemoRegistrationSerializer,
    RegistrationSerializer,
)
from metering_billing.serializers.model_serializers import UserSerializer
from metering_billing.serializers.serializer_utils import EmailSerializer
from metering_billing.services.user import user_service
from metering_billing.utils import now_utc
from rest_framework import serializers, status
from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("django.server")

POSTHOG_PERSON = settings.POSTHOG_PERSON
META = settings.META
SVIX_CONNECTOR = settings.SVIX_CONNECTOR


class LoginViewMixin(KnoxLoginView):
    authentication_classes = [BasicAuthentication]
    permission_classes = [AllowAny]


class LogoutViewMixin(KnoxLogoutView):
    permission_classes = [AllowAny]


class LoginView(LoginViewMixin, APIView):
    @extend_schema(
        request=inline_serializer(
            name="LoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="LoginSuccess",
                fields={
                    "detail": serializers.CharField(),
                    "token": serializers.CharField(),
                    "user": UserSerializer(),
                },
            ),
            400: inline_serializer(
                name="LoginFailure",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                {"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST
            )

        if data is None:
            return Response(
                {"detail": "No data provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        username = data.get("username")
        password = data.get("password")
        if username is None or password is None:
            return Response(
                {"detail": "Please provide username and password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(username=username, password=password)

        if user is None:
            return JsonResponse(
                {"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST
            )

        user_team = user.team
        if not all(
            [
                x != Organization.OrganizationType.EXTERNAL_DEMO
                for x in user_team.organizations.all().values_list(
                    "organization_type", flat=True
                )
            ]
        ):
            return JsonResponse(
                {"detail": "Cannot login in to Lotus app with a demo account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else username,
            event="succesful login",
            properties={"organization": user.organization.organization_name},
        )
        token = AuthToken.objects.create(user)
        return Response(
            {
                "detail": "Successfully logged in.",
                "token": token[1],
                "user": UserSerializer(user).data,
            }
        )


class DemoLoginView(LoginViewMixin, APIView):
    @extend_schema(
        request=inline_serializer(
            name="DemoLoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="DemoLoginSuccess",
                fields={
                    "detail": serializers.CharField(),
                    "token": serializers.CharField(),
                    "user": UserSerializer(),
                },
            ),
            400: inline_serializer(
                name="DemoLoginFailure",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                {"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST
            )

        if data is None:
            return Response(
                {"detail": "No data provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        username = data.get("username")
        password = data.get("password")

        if username is None or password is None:
            return Response(
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
            POSTHOG_PERSON if POSTHOG_PERSON else username,
            event="succesful login",
            properties={"organization": user.organization.organization_name},
        )
        token = AuthToken.objects.create(user)
        return Response(
            {
                "detail": "Successfully logged in.",
                "token": token[1],
                "user": UserSerializer(user).data,
            }
        )


class LogoutView(LogoutViewMixin):
    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                name="LogoutSuccess",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="LogoutFailure",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"detail": "You're not logged in."}, status=status.HTTP_400_BAD_REQUEST
            )
        return super().post(request, format)


class InitResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=EmailSerializer,
        responses={
            200: inline_serializer(
                name="InitResetPasswordSuccess",
                fields={
                    "email": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user_service.init_reset_password(email=email)

        return JsonResponse({"email": email})


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=inline_serializer(
            name="ResetPasswordRequest",
            fields={
                "userId": serializers.CharField(),
                "password": serializers.CharField(),
                "token": serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="ResetPasswordSuccess",
                fields={
                    "detail": serializers.CharField(),
                    "token": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        """Verifies the token and resets the password."""
        user_id = request.data.get("userId", None)
        raw_password = request.data.get("password", None)
        token = request.data.get("token", None)

        if not (user_id and raw_password and token):
            raise InvalidRequest(
                "Request must have the following parameters: (userId, password, token)"
            )

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
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                name="SessionSuccess",
                fields={
                    "isAuthenticated": serializers.BooleanField(),
                },
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        resp = {
            "isAuthenticated": request.user.is_authenticated,
        }
        if request.user.is_authenticated:
            resp["organization_id"] = (
                "org_" + request.user.organization.organization_id.hex
            )
        return JsonResponse(resp)


@extend_schema(
    request=RegistrationSerializer,
    responses={
        200: inline_serializer(
            name="RegistrationSuccess",
            fields={
                "detail": serializers.CharField(),
                "token": serializers.CharField(),
                "user": UserSerializer(),
            },
        ),
        400: inline_serializer(
            name="RegistrationFailure",
            fields={
                "detail": serializers.CharField(),
            },
        ),
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
        organization_name = reg_dict["organization_name"]

        existing_user_num = User.objects.filter(username=username).count()
        if existing_user_num > 0:
            raise DuplicateUser("User with username already exists")
        existing_user_num = User.objects.filter(email=email).count()
        if existing_user_num > 0:
            raise DuplicateUser("User with email already exists")

        if invite_token is not None and invite_token != "null":
            now = now_utc()
            try:
                token = TeamInviteToken.objects.get(
                    token=invite_token, expire_at__gt=now
                )
            except TeamInviteToken.DoesNotExist:
                raise RegistrationFailure("Invalid invite token")
            if token.email != email:
                raise RegistrationFailure("Email does not match invite token")
            team = token.team
            org = (
                Organization.objects.filter(team=team)
                .order_by("-organization_type")
                .first()
            )
        else:
            # Organization doesn't exist yet
            existing_org_num = Organization.objects.filter(
                organization_name=organization_name,
            ).count()
            if existing_org_num > 0:
                raise DuplicateOrganization(
                    "Organization environment with company name already exists"
                )
            team = Team.objects.create(name=organization_name)
            org = Organization.objects.create(
                organization_name=organization_name,
                team=team,
                organization_type=Organization.OrganizationType.DEVELOPMENT,
            )
            token = None
            # if META:
            #     lotus_python.create_customer(
            #         customer_id=org.organization_id,
            #         name=org.organization_name,
            #     )

        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            organization=org,
            team=team,
        )
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else username,
            event="register",
            properties={"organization": org.organization_name},
        )
        if token:
            token.delete()
        return Response(
            {
                "detail": "Successfully registered.",
                "token": AuthToken.objects.create(user)[1],
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    request=DemoRegistrationSerializer,
    responses={
        200: inline_serializer(
            name="DemoRegistrationSuccess",
            fields={
                "detail": serializers.CharField(),
                "token": serializers.CharField(),
                "user": UserSerializer(),
            },
        ),
        400: inline_serializer(
            name="DemoRegistrationFailure",
            fields={
                "detail": serializers.CharField(),
            },
        ),
    },
)
class DemoRegisterView(LoginViewMixin, APIView):
    def post(self, request, format=None):
        start = time.time()
        serializer = DemoRegistrationSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        reg_dict = serializer.validated_data["register"]
        username = reg_dict["username"]
        email = reg_dict["email"]
        password = reg_dict["password"]
        organization_name = "demo_" + username  # different

        existing_user_num = User.objects.filter(username=username).count()
        if existing_user_num > 0:
            raise DuplicateUser("User with username already exists")
        existing_user_num = User.objects.filter(email=email).count()
        if existing_user_num > 0:
            raise DuplicateUser("User with email already exists")

        user = setup_demo4(
            organization_name,
            username,
            email,
            password,
            org_type=Organization.OrganizationType.EXTERNAL_DEMO,
        )
        logger.info("setup_demo4 took %s seconds", time.time() - start)
        logger.info(f"Demo user {user} created")
        user.organization.organization_type = (
            Organization.OrganizationType.EXTERNAL_DEMO
        )
        user.organization.save()

        posthog.capture(
            username,
            event="demo_register",
            properties={"organization": user.organization.organization_name},
        )
        _, token = AuthToken.objects.create(user)
        user_data = UserSerializer(user).data
        logger.info(
            f"Token {token} created for user {user_data}, with org {user.organization}"
        )
        return Response(
            {
                "detail": "Successfully registered.",
                "token": token,
                "user": user_data,
            },
            status=status.HTTP_201_CREATED,
        )
