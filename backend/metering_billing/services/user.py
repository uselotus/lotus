import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from rest_framework.authtoken.models import Token

logger = logging.getLogger("django.server")
DEFAULT_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL


class UserService(object):
    def __init__(self, User):
        self.User = User

    def get(self, user_id=None, email=None):
        try:
            if user_id:
                return self.User.objects.get(id=user_id)
            if email:
                return self.User.objects.get(email=email.lower())
        except User.DoesNotExist:
            return None

    def get_or_create_token(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return token

    def send_reset_password_email(self, reset_url, to):
        subject = "Reset Your Password"
        body = f"Use this link to reset your password: {reset_url}"
        from_email = f"Lotus <{DEFAULT_FROM_EMAIL}>"
        html = """
            <p>Please <a href={url}>reset your password</a></p>""".format(
            url=reset_url
        )
        msg = EmailMultiAlternatives(subject, body, from_email, [to])
        msg.attach_alternative(html, "text/html")
        msg.tags = ["reset_password"]
        msg.track_clicks = True
        try:
            msg.send()
        except BadHeaderError:
            logger.error("Invalid header found.")
            return False

        return True

    def init_reset_password(self, email):
        """Given an email, creates a token and emails the user a reset link."""

        # For security reasons, we don't error if the user doesn't exist
        # since bad-actors cannot deduce which users exist
        user = None
        user = self.get(email=email)
        if not user:
            return False

        token = default_token_generator.make_token(user)
        path = "set-new-password?token=%s&userId=%s" % (token, user.id)
        password_reset_url = "%s/%s" % (settings.APP_URL, path)

        self.send_reset_password_email(reset_url=password_reset_url, to=email)

        return True

    def reset_password(self, user_id, raw_password, token):
        """Given a valid token, update  user's password."""
        user = self.get(user_id=user_id)
        if not user:
            return False

        if not default_token_generator.check_token(user, token):
            logger.info(
                {
                    "message": "User submitted invalid reset password token",
                    "userId": user.id,
                }
            )
            return False

        user.set_password(raw_password)
        user.save()
        return user


User = get_user_model()
user_service = UserService(User=User)
