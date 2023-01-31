from django.core.management.base import BaseCommand

from metering_billing.models import Event, User


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--email",
            help="email for the user to delete",
        )

    def handle(self, *args, **options):
        if options["email"]:
            user = User.objects.get(email=options["email"])
            team = user.team
            organizations = team.organizations.all()
            Event.objects.filter(organization__in=organizations).delete()
            team.delete()
