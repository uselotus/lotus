from django.utils.text import slugify

from metering_billing.models import Organization


def get_bucket_name(organization):
    team = organization.team
    team_organizations = team.organizations.all()
    # if the team has a prod organization, make them their own bucket
    if (
        team_organizations.filter(
            organization_type__in=[
                Organization.OrganizationType.PRODUCTION,
                Organization.OrganizationType.DEVELOPMENT,
            ]
        ).count()
        > 0
    ):
        bucket_name = "prod-" + team.team_id.hex + "-" + slugify(team.name)
        prod = True
    else:
        bucket_name = "dev"
        prod = False

    return bucket_name, prod
