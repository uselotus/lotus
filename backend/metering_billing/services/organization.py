from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from metering_billing.models import Organization, OrganizationInviteToken, User


class OrganizationService(object):
    def __init__(self):
        pass

    def get(self, user_id=None, organization_id=None):
        try:
            if organization_id:
                return Organization.objects.filter(id=organization_id)
            if user_id:
                user = User.objects.get(id=user_id)
                return Organization.objects.filter(org_users__contains=user)
        except exceptions.ObjectDoesNotExist as e:
            return None

    def get_or_create_token(self, organization_id, user_id):
        token, _ = OrganizationInviteToken.objects.get_or_create(
            organization_id=organization_id, user_id=user_id
        )
        return token

    def send_invite_email(self, reset_url, organization_name, to):
        subject = f"Join {organization_name} in Lotus"
        body = f"Use this link to join {organization_name} team: {reset_url}"
        from_email = f"Lotus <{settings.DEFAULT_FROM_EMAIL}>"
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

    def invite(self, user_id, email):
        """Given an email, creates a token and emails the user a reset link."""

        # For security reasons, we don't error if the user doesn't exist
        # since bad-actors cannot deduce which users exist
        organization = self.get(user_id=user_id).first()

        if not organization:
            return False

        token_object = (
            self.get_or_create_token(organization_id=organization.id, user_id=user_id),
        )
        path = "register?token=%s" % (token_object.token)
        password_reset_url = "%s/%s" % (settings.APP_URL, path)

        self.send_invite_email(
            reset_url=password_reset_url,
            organization_name=organization.company_name,
            to=email,
        )

        return True


organization_service = OrganizationService()
