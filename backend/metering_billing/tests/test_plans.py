import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import Plan, PlanVersion, Subscription, SubscriptionRecord
from metering_billing.utils import now_utc
from metering_billing.utils.enums import *
from model_bakery import baker
from rest_framework import serializers, status
from rest_framework.test import APIClient


@pytest.fixture
def plan_test_common_setup(
    generate_org_and_api_key, add_product_to_org, add_users_to_org, add_customers_to_org
):
    def do_plan_test_common_setup():
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
                "flat_fee_billing_type": FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
                "status": PLAN_VERSION_STATUS.ACTIVE,
                "flat_rate": 1000,
            },
        }
        setup_dict["plan_update_payload"] = {
            "plan_name": "change_plan_name",
        }
        setup_dict["plan_version_payload"] = {
            "description": "test_plan_version_description",
            "flat_fee_billing_type": FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            "make_active": True,
            "flat_rate": 100,
        }
        setup_dict["plan_version_update_payload"] = {
            "description": "changed",
        }

        return setup_dict

    return do_plan_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestCreatePlan:
    def test_create_plan_basic(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()

        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "display_version" in response.data
        assert (
            response.data["display_version"]["version"] == 1
        )  # should initialize with v1
        assert response.data["created_by"] == setup_dict["user"].username
        assert (
            response.data["display_version"]["created_by"]
            == setup_dict["user"].username
        )

    def test_plan_dont_specify_version_fails_doesnt_create_plan(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        setup_dict["plan_payload"].pop("initial_version")
        plan_before = Plan.objects.all().count()

        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan_after = Plan.objects.all().count()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert plan_before == plan_after
        assert "initial_version" in response.data

    def test_plan_with_repeated_id_fails(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        baker.make(Plan, plan_id="test-id")
        setup_dict["plan_payload"]["plan_id"] = "test-id"
        plan_before = Plan.objects.all().count()

        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan_after = Plan.objects.all().count()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert plan_before == plan_after
        assert "plan_id" in response.data


@pytest.mark.django_db(transaction=True)
class TestCreatePlanVersion:
    def test_create_new_version_as_active_works(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()

        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])

        # now add in the plan ID to the payload, and send a post request for the new version
        setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
        setup_dict["plan_version_payload"][
            "make_active_type"
        ] = MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_IMMEDIATELY
        setup_dict["plan_version_payload"][
            "replace_immediately_type"
        ] = REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_DONT_BILL
        response = setup_dict["client"].post(
            reverse("plan_version-list"),
            data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert PlanVersion.objects.all().count() == 2
        assert set(PlanVersion.objects.values_list("version", flat=True)) == set([1, 2])
        assert set(PlanVersion.objects.values_list("status", flat=True)) == set(
            [PLAN_VERSION_STATUS.ACTIVE, PLAN_VERSION_STATUS.INACTIVE]
        )
        assert response.data["created_by"] == setup_dict["user"].username
        assert len(plan.versions.all()) == 2

    def test_create_new_version_as_inactive_works(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()

        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert set(PlanVersion.objects.values_list("version", "status")) == set(
            [(1, PLAN_VERSION_STATUS.ACTIVE)]
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])

        # now add in the plan ID to the payload, and send a post request for the new version
        setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
        setup_dict["plan_version_payload"]["make_active"] = False
        response = setup_dict["client"].post(
            reverse("plan_version-list"),
            data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert PlanVersion.objects.all().count() == 2
        assert set(PlanVersion.objects.values_list("version", "status")) == set(
            [(1, PLAN_VERSION_STATUS.ACTIVE), (2, PLAN_VERSION_STATUS.INACTIVE)]
        )
        assert response.data["created_by"] == setup_dict["user"].username
        assert len(plan.versions.all()) == 2
        assert PlanVersion.objects.get(version=1) == plan.display_version

    def test_create_new_version_as_active_with_existing_subscriptions_grandfathering(
        self,
        plan_test_common_setup,
        add_subscription_to_org,
    ):
        setup_dict = plan_test_common_setup()
        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])
        plan_version = plan.display_version
        sub = add_subscription_to_org(
            setup_dict["org"], plan_version, setup_dict["customer"], now_utc()
        )
        # now add in the plan ID to the payload, and send a post request for the new version
        setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
        setup_dict["plan_version_payload"][
            "make_active_type"
        ] = MAKE_PLAN_VERSION_ACTIVE_TYPE.GRANDFATHER_ACTIVE
        response = setup_dict["client"].post(
            reverse("plan_version-list"),
            data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert PlanVersion.objects.all().count() == 2
        assert set(PlanVersion.objects.values_list("version", flat=True)) == set([1, 2])
        assert set(PlanVersion.objects.values_list("status", flat=True)) == set(
            [PLAN_VERSION_STATUS.ACTIVE, PLAN_VERSION_STATUS.GRANDFATHERED]
        )
        assert response.data["created_by"] == setup_dict["user"].username
        assert len(plan.versions.all()) == 2

    def test_create_new_version_as_active_with_existing_subscriptions_replace_on_renewal(
        self,
        plan_test_common_setup,
        add_subscription_to_org,
    ):
        setup_dict = plan_test_common_setup()

        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])
        plan_version = plan.display_version
        sub = add_subscription_to_org(
            setup_dict["org"], plan_version, setup_dict["customer"], now_utc()
        )

        # now add in the plan ID to the payload, and send a post request for the new version
        setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
        setup_dict["plan_version_payload"][
            "make_active_type"
        ] = MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_ON_ACTIVE_VERSION_RENEWAL
        response = setup_dict["client"].post(
            reverse("plan_version-list"),
            data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert PlanVersion.objects.all().count() == 2
        assert set(PlanVersion.objects.values_list("version", flat=True)) == set([1, 2])
        assert set(PlanVersion.objects.values_list("status", flat=True)) == set(
            [PLAN_VERSION_STATUS.ACTIVE, PLAN_VERSION_STATUS.RETIRING]
        )
        assert response.data["created_by"] == setup_dict["user"].username
        assert len(plan.versions.all()) == 2


@pytest.mark.django_db(transaction=True)
class TestUpdatePlan:
    def test_change_plan_name(self, plan_test_common_setup, add_subscription_to_org):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan_before = Plan.objects.all().count()
        plan_test_plan_before = Plan.objects.filter(
            plan_name="change_plan_name"
        ).count()
        plan_id = Plan.objects.all()[0].plan_id

        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": plan_id}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        plan_after = Plan.objects.all().count()
        plan_test_plan_after = Plan.objects.filter(plan_name="change_plan_name").count()
        assert response.status_code == status.HTTP_200_OK
        assert plan_before == plan_after
        assert plan_test_plan_before + 1 == plan_test_plan_after

    def test_change_plan_to_inactive_works(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan_before = Plan.objects.all().count()
        plans_inactive_before = Plan.objects.filter(status=PLAN_STATUS.ARCHIVED).count()
        plan_id = Plan.objects.all()[0].plan_id

        setup_dict["plan_update_payload"]["status"] = PLAN_STATUS.ARCHIVED
        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": plan_id}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        plan_after = Plan.objects.all().count()
        plans_inactive_after = Plan.objects.filter(status=PLAN_STATUS.ARCHIVED).count()
        assert response.status_code == status.HTTP_200_OK
        assert plan_before == plan_after
        assert plans_inactive_before + 1 == plans_inactive_after

    def test_change_plan_to_inactive_plan_has_active_subs_fails(
        self, plan_test_common_setup, add_subscription_to_org
    ):
        setup_dict = plan_test_common_setup()

        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])
        plan_version = plan.display_version
        sub = add_subscription_to_org(
            setup_dict["org"], plan_version, setup_dict["customer"], now_utc()
        )
        plan_before = Plan.objects.all().count()
        plans_inactive_before = Plan.objects.filter(status=PLAN_STATUS.ARCHIVED).count()
        plan_id = Plan.objects.all()[0].plan_id

        setup_dict["plan_update_payload"]["status"] = PLAN_STATUS.ARCHIVED
        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": plan_id}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        plan_after = Plan.objects.all().count()
        plans_inactive_after = Plan.objects.filter(status=PLAN_STATUS.ARCHIVED).count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert plan_before == plan_after
        assert plans_inactive_before == plans_inactive_after


@pytest.mark.django_db(transaction=True)
class TestUpdatePlanVersion:
    def test_change_plan_version_description(
        self, plan_test_common_setup, add_subscription_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan_version_before = PlanVersion.objects.all().count()
        plan_test_plan_before = PlanVersion.objects.filter(
            description="changed"
        ).count()
        version_id = PlanVersion.objects.all()[0].version_id

        response = setup_dict["client"].patch(
            reverse("plan_version-detail", kwargs={"version_id": version_id}),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )

        plan_version_after = PlanVersion.objects.all().count()
        plan_test_plan_after = PlanVersion.objects.filter(description="changed").count()
        assert response.status_code == status.HTTP_200_OK
        assert plan_version_before == plan_version_after
        assert plan_test_plan_before + 1 == plan_test_plan_after

    def test_change_plan_version_archived_works(
        self, plan_test_common_setup, add_subscription_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan_version_before = PlanVersion.objects.all().count()
        plan_test_plan_before = PlanVersion.objects.filter(
            status=PLAN_VERSION_STATUS.ARCHIVED
        ).count()
        version_id = PlanVersion.objects.all()[0].version_id

        setup_dict["plan_version_update_payload"][
            "status"
        ] = PLAN_VERSION_STATUS.ARCHIVED
        response = setup_dict["client"].patch(
            reverse("plan_version-detail", kwargs={"version_id": version_id}),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )

        plan_version_after = PlanVersion.objects.all().count()
        plan_test_plan_after = PlanVersion.objects.filter(
            status=PLAN_VERSION_STATUS.ARCHIVED
        ).count()
        assert response.status_code == status.HTTP_200_OK
        assert plan_version_before == plan_version_after
        assert plan_test_plan_before + 1 == plan_test_plan_after

    def test_change_plan_version_to_archived_has_active_subs_fails(
        self,
        plan_test_common_setup,
        add_subscription_to_org,
    ):
        setup_dict = plan_test_common_setup()

        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])
        plan_version = plan.display_version
        sub = add_subscription_to_org(
            setup_dict["org"], plan_version, setup_dict["customer"], now_utc()
        )
        plan_before = Plan.objects.all().count()
        plan_versions_archived_before = Plan.objects.filter(
            status=PLAN_VERSION_STATUS.ARCHIVED
        ).count()
        version_id = PlanVersion.objects.all()[0].version_id

        setup_dict["plan_version_update_payload"][
            "status"
        ] = PLAN_VERSION_STATUS.ARCHIVED
        response = setup_dict["client"].patch(
            reverse("plan_version-detail", kwargs={"version_id": version_id}),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )

        plan_after = Plan.objects.all().count()
        plan_versions_archived_after = Plan.objects.filter(
            status=PLAN_VERSION_STATUS.ARCHIVED
        ).count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert plan_before == plan_after
        assert plan_versions_archived_before == plan_versions_archived_after

    def test_change_plan_version_to_active_works(
        self, plan_test_common_setup, add_subscription_to_org
    ):
        setup_dict = plan_test_common_setup()

        # add in the plan, along with initial version
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"])
        first_plan_version = plan.display_version
        sub = add_subscription_to_org(
            setup_dict["org"], first_plan_version, setup_dict["customer"], now_utc()
        )

        # now add in the plan ID to the payload, and send a post request for the new version
        setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
        setup_dict["plan_version_payload"][
            "make_active_type"
        ] = MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_ON_ACTIVE_VERSION_RENEWAL
        response = setup_dict["client"].post(
            reverse("plan_version-list"),
            data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        # finally lets update the first one back to active
        setup_dict["plan_version_update_payload"]["status"] = PLAN_VERSION_STATUS.ACTIVE
        response = setup_dict["client"].patch(
            reverse(
                "plan_version-detail",
                kwargs={"version_id": first_plan_version.version_id},
            ),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert PlanVersion.objects.all().count() == 2
        assert set(PlanVersion.objects.values_list("version", flat=True)) == set([1, 2])
        assert set(PlanVersion.objects.values_list("status", flat=True)) == set(
            [PLAN_VERSION_STATUS.ACTIVE, PLAN_VERSION_STATUS.INACTIVE]
        )
        assert len(plan.versions.all()) == 2

    # test creating  a new plan and then creating 2 new versions of that plan and checking the output of getplans
    # def test_create_multiple_inactive_versions(self, plan_test_common_setup):
    #     setup_dict = plan_test_common_setup()

    #     # add in the plan, along with initial version
    #     response = setup_dict["client"].post(
    #         reverse("plan-list"),
    #         data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
    #         content_type="application/json",
    #     )
    #     plan = Plan.objects.get(plan_id=response.data["plan_id"])
    #     first_plan_version = plan.display_version

    #     # now add in the plan ID to the payload, and send a post request for the new version
    #     setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
    #     setup_dict["plan_version_payload"]["make_active"] = False
    #     response = setup_dict["client"].post(
    #         reverse("plan_version-list"),
    #         data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
    #         content_type="application/json",
    #     )

    #     # finally lets update the first one back to active
    #     setup_dict["plan_version_update_payload"]["status"] = PLAN_VERSION_STATUS.ACTIVE
    #     response = setup_dict["client"].patch(
    #         reverse(
    #             "plan_version-detail",
    #             kwargs={"version_id": first_plan_version.version_id},
    #         ),
    #         data=json.dumps(
    #             setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
    #         ),
    #         content_type="application/json",
    #     )

    #     # now add in the plan ID to the payload, and send a post request for the new version
    #     setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
    #     setup_dict["plan_version_payload"]["make_active"] = False
    #     response = setup_dict["client"].post(
    #         reverse("plan_version-list"),
    #         data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
    #         content_type="application/json",
    #     )

    #     # finally lets update the first one back to active

    #     ##response for api/plans
    #     response = setup_dict["client"].get(reverse("plan-list"))
    #     assert response.status_code == status.HTTP_200_OK
    #     assert len(response.data.versions) == 3
