import pytest
from django.urls import reverse
from lotus.backend.metering_billing.utils.enums import PLAN_DURATION, PLAN_VERSION_STATUS, TAG_GROUP
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def org_test_common_setup(
    generate_org_and_api_key, add_product_to_org, add_users_to_org, add_customers_to_org
):
    def do_org_test_common_setup():
        # set up organizations and api keys
        org, _ = generate_org_and_api_key()
        setup_dict = {
            "org": org,
        }
        # set up the client with the user authenticated
        client = APIClient()
        (user,) = add_users_to_org(org, n=1)
        (customer,) = add_customers_to_org(org, n=1)
        client.force_authenticate(user=user)
        setup_dict["user"] = user
        setup_dict["customer"] = customer
        setup_dict["client"] = client
        setup_dict["product"] = add_product_to_org(org)
        setup_dict["plan_payload"] = {
            "plan_name": "test_plan",
            "plan_duration": PLAN_DURATION.MONTHLY,
            "product_id": setup_dict["product"].product_id,
            "initial_version": {
                "status": PLAN_VERSION_STATUS.ACTIVE,
                "recurring_charges": [
                    {
                        "name": "test_recurring_charge",
                        "charge_timing": "in_advance",
                        "amount": 1000,
                        "charge_behavior": "prorate",
                    }
                ],
            },
        }
        setup_dict["plan_update_payload"] = {
            "plan_name": "change_plan_name",
        }
        setup_dict["plan_version_payload"] = {
            "description": "test_plan_version_description",
            "make_active": True,
            "recurring_charges": [
                {
                    "name": "test_recurring_charge",
                    "charge_timing": "in_advance",
                    "amount": 100,
                    "charge_behavior": "prorate",
                }
            ],
        }
        setup_dict["plan_version_update_payload"] = {
            "description": "changed",
        }

        return setup_dict

    return do_org_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestOrganizationTags:
    def test_add_tags_to_org(self, org_test_common_setup):
        setup_dict = org_test_common_setup()
        org = setup_dict["org"]
        client = setup_dict["client"]
        payload = {
            "plan_tags": [
                {"tag_name": "test_tag1", "tag_color": "blue", "tag_hex": "#ffffff"},
                {"tag_name": "test_tag2", "tag_color": "red", "tag_hex": "#ffffff"},
            ]
        }
        response = client.patch(
            reverse(
                "organization-detail",
                kwargs={"organization_id": "org_" + org.organization_id.hex},
            ),
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert sorted(
            list(
                org.tags.filter(tag_group=TAG_GROUP.PLAN).values_list(
                    "tag_name", flat=True
                )
            )
        ) == [
            "test_tag1",
            "test_tag2",
        ]

    def test_remove_tags_from_org(self, org_test_common_setup):
        setup_dict = org_test_common_setup()
        org = setup_dict["org"]
        client = setup_dict["client"]
        payload = {
            "plan_tags": [
                {"tag_name": "test_tag1", "tag_color": "blue", "tag_hex": "#ffffff"},
                {"tag_name": "test_tag2", "tag_color": "red", "tag_hex": "#ffffff"},
            ]
        }
        response = client.patch(
            reverse(
                "organization-detail",
                kwargs={"organization_id": "org_" + org.organization_id.hex},
            ),
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert sorted(
            list(
                org.tags.filter(tag_group=TAG_GROUP.PLAN).values_list(
                    "tag_name", flat=True
                )
            )
        ) == [
            "test_tag1",
            "test_tag2",
        ]
        payload = {
            "plan_tags": [
                {"tag_name": "test_tag1", "tag_color": "blue", "tag_hex": "#ffffff"},
            ]
        }
        response = client.patch(
            reverse(
                "organization-detail",
                kwargs={"organization_id": "org_" + org.organization_id.hex},
            ),
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert sorted(
            list(
                org.tags.filter(tag_group=TAG_GROUP.PLAN).values_list(
                    "tag_name", flat=True
                )
            )
        ) == [
            "test_tag1",
        ]
