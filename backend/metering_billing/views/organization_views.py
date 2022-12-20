from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth import parse_organization
from metering_billing.models import OrganizationInviteToken
from metering_billing.permissions import ValidOrganization
from metering_billing.serializers.model_serializers import *
from metering_billing.utils import now_plus_day
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

POSTHOG_PERSON = settings.POSTHOG_PERSON
DEFAULT_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL


class InviteView(APIView):
    permission_classes = [IsAuthenticated & ValidOrganization]

    @extend_schema(
        request=inline_serializer(
            name="InviteRequestSerializer",
            fields={
                "email": serializers.EmailField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="InviteResponseSerializer",
                fields={"email": serializers.EmailField()},
            )
        },
    )
    def post(self, request, *args, **kwargs):
        email = request.data.get("email", None)
        user = request.user
        organization = request.organization

        token_object, created = OrganizationInviteToken.objects.get_or_create(
            organization=organization, email=email, defaults={"user": user}
        )
        if not created:
            token_object.user = user
            token_object.expire_at = now_plus_day()
            token_object.save()
        path = "register?token=%s" % (token_object.token)
        password_reset_url = "%s/%s" % (settings.APP_URL, path)

        send_invite_email(
            reset_url=password_reset_url,
            organization_name=organization.company_name,
            to=email,
        )

        return Response({"email": email}, status=status.HTTP_200_OK)


def send_invite_email(reset_url, organization_name, to):
    subject = f"Join {organization_name} in Lotus"
    body = f"Use this link to join {organization_name} team: {reset_url}"
    from_email = f"Lotus <{DEFAULT_FROM_EMAIL}>"
    html = """
            <p>Register to <a href={url}>join {organization_name}</a> team</p>""".format(
        url=reset_url, organization_name=organization_name
    )
    msg = EmailMultiAlternatives(subject, body, from_email, [to])
    msg.attach_alternative(html, "text/html")
    msg.tags = ["join_team"]
    msg.track_clicks = True
    try:
        msg.send()
    except BadHeaderError:
        print("Invalid header found.")
        return False

    return True
