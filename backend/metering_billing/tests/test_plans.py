import json
import urllib.parse

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from metering_billing.models import Customer, Feature, Plan, PlanVersion, Tag
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.utils import now_utc
from metering_billing.utils.enums import PLAN_DURATION
from rest_framework import status
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
            "initial_version": {
                "currency_code": "USD",
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
            "plan_description": "test_plan_version_description",
        }
        setup_dict["plan_version_payload"] = {
            "currency_code": "USD",
            "recurring_charges": [
                {
                    "name": "test_recurring_charge",
                    "charge_timing": "in_advance",
                    "amount": 100,
                    "charge_behavior": "prorate",
                }
            ],
        }
        setup_dict["plan_version_update_payload"] = {}

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
        print(response.data)
        assert response.status_code == status.HTTP_201_CREATED

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
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))

        # now add in the plan ID to the payload, and send a post request for the new version
        setup_dict["plan_version_payload"]["plan_id"] = plan.plan_id
        response = setup_dict["client"].post(
            reverse("plan_version-list"),
            data=json.dumps(setup_dict["plan_version_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert PlanVersion.objects.all().count() == 2
        assert len(plan.versions.all()) == 2


@pytest.mark.django_db(transaction=True)
class TestPlanOperations:
    def test_add_tags_empty_before(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        tags_before = set(plan.tags.values("tag_name"))
        assert len(tags_before) == 0

        tags_payload = {"tags": [{"tag_name": "test_tag"}, {"tag_name": "test_tag_2"}]}
        response = setup_dict["client"].post(
            reverse("plan-tags_add", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(tags_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        tags_after = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_after) == 2
        assert "test_tag" in tags_after
        assert "test_tag_2" in tags_after

    def test_add_tags_different_capitalization_doesnt_duplicate(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        tags_before = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_before) == 0

        tags_payload = {"tags": [{"tag_name": "test_tag"}, {"tag_name": "TEST_tag"}]}
        response = setup_dict["client"].post(
            reverse("plan-tags_add", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(tags_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        tags_after = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_after) == 1
        assert "test_tag" in tags_after

        tags_payload_2 = {"tags": [{"tag_name": "TEST_TAG"}]}
        response = setup_dict["client"].post(
            reverse("plan-tags_add", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(tags_payload_2, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        tags_after_2 = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_after_2) == 1
        assert "test_tag" in tags_after_2

    def test_remove_tags_including_nonexistent(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        # oen tag for case exact, one for case insensitive, one to make sure nonexistent doesn't break
        tag = Tag.objects.create(tag_name="test_tag", organization=setup_dict["org"])
        tag2 = Tag.objects.create(tag_name="test_tag_2", organization=setup_dict["org"])
        tag3 = Tag.objects.create(tag_name="test_tag_3", organization=setup_dict["org"])

        plan.tags.add(tag)
        plan.tags.add(tag2)
        plan.tags.add(tag3)

        tags_before = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_before) == 3

        tags_payload = {
            "tags": [
                {"tag_name": "test_tag"},
                {"tag_name": "TEST_tag_2"},
                {"tag_name": "test_tag_4"},
            ]
        }
        response = setup_dict["client"].post(
            reverse("plan-tags_remove", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(tags_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        tags_after = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_after) == 1
        assert "test_tag_3" in tags_after

    def test_set_tags(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        # want to cover all cases for set: previously in, after not, previously not in, after in, previously in, after in
        tag = Tag.objects.create(tag_name="test_tag", organization=setup_dict["org"])
        tag2 = Tag.objects.create(tag_name="TEST_tag_2", organization=setup_dict["org"])
        Tag.objects.create(tag_name="test_tag_3", organization=setup_dict["org"])

        plan.tags.add(tag)
        plan.tags.add(tag2)

        tags_before = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_before) == 2

        tags_payload = {
            "tags": [{"tag_name": "test_tag_2"}, {"tag_name": "test_tag_3"}]
        }
        response = setup_dict["client"].post(
            reverse("plan-tags_set", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(tags_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        tags_after = set(plan.tags.values_list("tag_name", flat=True))
        assert len(tags_after) == 2
        assert "TEST_tag_2" in tags_after
        assert "test_tag_3" in tags_after

    def test_add_new_feature(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        # we want to test that when we add it to the plan, it doesn't add it to any deleted plan versions, but adds it to both active and inactive plan versions
        first_version = plan.versions.first()
        first_version.plan_version_name = "active_version"
        first_version.save()
        assert first_version.features.count() == 0
        inactive_version = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            plan_version_name="inactive_version",
            not_active_before=now_utc() - relativedelta(days=10),
            not_active_after=now_utc() - relativedelta(days=5),
        )
        assert inactive_version.features.count() == 0
        deleted_version = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            plan_version_name="deleted_version",
            not_active_before=now_utc() - relativedelta(days=10),
            not_active_after=now_utc() - relativedelta(days=5),
            deleted=now_utc() - relativedelta(days=5),
        )
        assert deleted_version.features.count() == 0

        feature = Feature.objects.create(
            feature_name="test_feature",
            feature_description="test_description",
            organization=setup_dict["org"],
        )
        feature_id = feature.feature_id
        feature_payload = {"feature_id": feature_id, "all_versions": True}
        response = setup_dict["client"].post(
            reverse("plan-features_add", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(feature_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert first_version.features.count() == 1
        assert inactive_version.features.count() == 1
        assert deleted_version.features.count() == 0

        # now we create a new feature, but instead of all_versions, we specify version_ids and make sure it only adds it to the active version
        feature2 = Feature.objects.create(
            feature_name="test_feature2",
            feature_description="test_description2",
            organization=setup_dict["org"],
        )
        feature2_id = feature2.feature_id

        feature2_payload = {
            "feature_id": feature2_id,
            "version_ids": [first_version.version_id],
        }
        response = setup_dict["client"].post(
            reverse("plan-features_add", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(feature2_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert first_version.features.count() == 2
        assert inactive_version.features.count() == 1
        assert deleted_version.features.count() == 0

    def test_edit_not_active_after_no_longer_in_list_plans(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))

        list_plans = setup_dict["client"].get(reverse("plan-list"))
        assert len(list_plans.data) == 1

        setup_dict["plan_update_payload"]["not_active_after"] = now_utc()
        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": response.data["plan_id"]}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        list_plans = setup_dict["client"].get(
            reverse("plan-list")
            + "?"
            + urllib.parse.urlencode({"active_on": now_utc().isoformat()})
        )
        assert len(list_plans.data) == 0

    def test_edit_not_active_before_no_longer_in_list_plans(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        plan.not_active_after = now_utc() + relativedelta(days=3)
        plan.save()

        list_plans = setup_dict["client"].get(reverse("plan-list"))
        assert len(list_plans.data) == 1

        setup_dict["plan_update_payload"][
            "not_active_before"
        ] = now_utc() + relativedelta(days=10)
        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": response.data["plan_id"]}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        # check if we just update this then before and after are confusing
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        plan.not_active_after = now_utc() + relativedelta(days=10)
        plan.save()
        setup_dict["plan_update_payload"][
            "not_active_before"
        ] = now_utc() + relativedelta(days=3)
        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": plan.plan_id}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        list_plans = setup_dict["client"].get(
            reverse("plan-list")
            + "?"
            + urllib.parse.urlencode({"active_on": now_utc().isoformat()})
        )
        assert len(list_plans.data) == 0

    def test_update_plan_name_description_works(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))

        setup_dict["plan_update_payload"]["plan_name"] = "new_plan_name"
        setup_dict["plan_update_payload"]["plan_description"] = "new_plan_description"
        response = setup_dict["client"].patch(
            reverse("plan-detail", kwargs={"plan_id": response.data["plan_id"]}),
            data=json.dumps(setup_dict["plan_update_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        assert plan.plan_name == "new_plan_name"
        assert plan.plan_description == "new_plan_description"

    def test_delete_including_fail_with_subscription(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        add_subscription_record_to_org(
            setup_dict["org"], plan.versions.first(), setup_dict["customer"]
        )

        # susbcription active, should fail
        response = setup_dict["client"].post(
            reverse("plan-delete", kwargs={"plan_id": response.data["plan_id"]})
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # susbcription inactive, should work
        plan.versions.first().subscription_records.first().cancel_subscription()
        response = setup_dict["client"].post(
            reverse("plan-delete", kwargs={"plan_id": plan.plan_id})
        )
        assert response.status_code == status.HTTP_200_OK
        assert Plan.objects.all().count() == 0


@pytest.mark.django_db(transaction=True)
class TestPlanVersionOperations:
    """
    Tests to write:
    chaneg active dates
    """

    def test_add_target_customer_to_version_plain(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        version = plan.versions.first()
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert version.is_custom is False

        add_target_customer_payload = {
            "customer_ids": [setup_dict["customer"].customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-add_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(add_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 1
        assert version.is_custom is True

    def test_add_target_customer_to_version_subscriptionrecord_exists(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        version = plan.versions.first()
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert version.is_custom is False

        add_subscription_record_to_org(
            setup_dict["org"], version, setup_dict["customer"]
        )

        new_customer = Customer.objects.create(
            customer_name="new_customer",
            customer_id="new_customer",
            organization=setup_dict["org"],
            email="new_customer@new_customer.com",
        )

        add_target_customer_payload = {
            "customer_ids": [new_customer.customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-add_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(add_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        add_target_customer_payload = {
            "customer_ids": [
                setup_dict["customer"].customer_id,
                new_customer.customer_id,
            ],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-add_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(add_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 2
        assert version.is_custom is True

    def test_remove_target_customer_plain(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        version = plan.versions.first()
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert version.is_custom is False

        add_target_customer_payload = {
            "customer_ids": [setup_dict["customer"].customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-add_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(add_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 1
        assert version.is_custom is True

        remove_target_customer_payload = {
            "customer_ids": [setup_dict["customer"].customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-remove_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(remove_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert (
            version.is_custom is True
        )  #!!!! tough but don't assume no customer means public

    def test_remove_target_customer_subscriptionrecord_exists(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        version = plan.versions.first()
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert version.is_custom is False

        add_subscription_record_to_org(
            setup_dict["org"], version, setup_dict["customer"]
        )
        add_target_customer_payload = {
            "customer_ids": [setup_dict["customer"].customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-add_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(add_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 1
        assert version.is_custom is True

        remove_target_customer_payload = {
            "customer_ids": [setup_dict["customer"].customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-remove_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(remove_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_make_public_works(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        version = plan.versions.first()
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert version.is_custom is False

        add_subscription_record_to_org(
            setup_dict["org"], version, setup_dict["customer"]
        )
        add_target_customer_payload = {
            "customer_ids": [setup_dict["customer"].customer_id],
        }
        response = setup_dict["client"].post(
            reverse(
                "plan_version-add_target_customer",
                kwargs={"version_id": version.version_id},
            ),
            data=json.dumps(add_target_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 1
        assert version.is_custom is True

        response = setup_dict["client"].post(
            reverse(
                "plan_version-make_public",
                kwargs={"version_id": version.version_id},
            ),
        )
        assert response.status_code == status.HTTP_200_OK

        version = PlanVersion.objects.get(id=version.id)
        version_customers = version.target_customers.all()
        assert version_customers.count() == 0
        assert version.is_custom is False

    def test_add_feature_to_plan_version(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        # we want to test that when we add it to the plan, it doesn't add it to any deleted plan versions, but adds it to both active and inactive plan versions
        first_version = plan.versions.first()
        first_version.plan_version_name = "active_version"
        first_version.save()
        assert first_version.features.count() == 0
        second_version = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            plan_version_name="inactive_version",
        )
        assert second_version.features.count() == 0

        feature = Feature.objects.create(
            feature_name="test_feature",
            feature_description="test_description",
            organization=setup_dict["org"],
        )
        feature_id = feature.feature_id
        feature_payload = {"feature_id": feature_id}
        response = setup_dict["client"].post(
            reverse(
                "plan_version-features_add",
                kwargs={"version_id": first_version.version_id},
            ),
            data=json.dumps(feature_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert first_version.features.count() == 1
        assert second_version.features.count() == 0

    def test_set_replacement_for_plan(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        # we want to test that when we add it to the plan, it doesn't add it to any deleted plan versions, but adds it to both active and inactive plan versions
        first_version = plan.versions.first()
        first_version.plan_version_name = "active_version"
        first_version.save()
        second_version = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            plan_version_name="inactive_version",
        )
        assert first_version.replace_with is None

        replace_with_payload = {"replace_with": second_version.version_id}
        response = setup_dict["client"].post(
            reverse(
                "plan_version-set_replacement",
                kwargs={"version_id": first_version.version_id},
            ),
            data=json.dumps(replace_with_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        first_version = PlanVersion.objects.get(id=first_version.id)
        assert first_version.replace_with == second_version

    def test_make_replacement_for_plan(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        # we want to test that when we add it to the plan, it doesn't add it to any deleted plan versions, but adds it to both active and inactive plan versions
        first_version = plan.versions.first()
        first_version.plan_version_name = "active_version"
        first_version.save()
        second_version = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            plan_version_name="inactive_version",
        )
        assert first_version.replace_with is None

        replace_with_payload = {"versions_to_replace": [first_version.version_id]}
        response = setup_dict["client"].post(
            reverse(
                "plan_version-make_replacement",
                kwargs={"version_id": second_version.version_id},
            ),
            data=json.dumps(replace_with_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        first_version = PlanVersion.objects.get(id=first_version.id)
        assert first_version.replace_with == second_version

    def test_delete_plan_version_including_subscription(
        self, plan_test_common_setup, add_subscription_record_to_org
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        first_version = plan.versions.first()
        first_version.plan_version_name = "active_version"
        first_version.save()
        PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            plan_version_name="inactive_version",
        )
        add_subscription_record_to_org(
            setup_dict["org"], first_version, setup_dict["customer"]
        )

        # susbcription active, should fail
        response = setup_dict["client"].post(
            reverse(
                "plan_version-delete", kwargs={"version_id": first_version.version_id}
            )
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # susbcription inactive, should work
        plan.versions.first().subscription_records.first().cancel_subscription()
        response = setup_dict["client"].post(
            reverse(
                "plan_version-delete", kwargs={"version_id": first_version.version_id}
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert Plan.objects.all().count() == 1
        assert PlanVersion.objects.all().count() == 1
        assert Plan.objects.first().versions.count() == 1

    def test_edit_not_active_after_no_longer_in_list_plans(
        self,
        plan_test_common_setup,
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        first_version = plan.versions.first()

        listed_plan = setup_dict["client"].get(reverse("plan-list")).data[0]
        assert len(listed_plan["versions"]) == 1

        setup_dict["plan_version_update_payload"]["not_active_after"] = now_utc()
        response = setup_dict["client"].patch(
            reverse(
                "plan_version-detail", kwargs={"version_id": first_version.version_id}
            ),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        listed_plan = (
            setup_dict["client"]
            .get(
                reverse("plan-list")
                + "?"
                + urllib.parse.urlencode({"active_on": now_utc().isoformat()})
            )
            .data[0]
        )
        assert len(listed_plan["versions"]) == 0

    def test_edit_not_active_before_no_longer_in_list_plans(
        self, plan_test_common_setup
    ):
        setup_dict = plan_test_common_setup()
        response = setup_dict["client"].post(
            reverse("plan-list"),
            data=json.dumps(setup_dict["plan_payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        plan = Plan.objects.get(plan_id=response.data["plan_id"].replace("plan_", ""))
        first_version = plan.versions.first()

        listed_plan = setup_dict["client"].get(reverse("plan-list")).data[0]
        assert len(listed_plan["versions"]) == 1

        first_version.not_active_after = now_utc() + relativedelta(days=3)
        first_version.save()

        setup_dict["plan_version_update_payload"][
            "not_active_before"
        ] = now_utc() + relativedelta(days=10)
        response = setup_dict["client"].patch(
            reverse(
                "plan_version-detail", kwargs={"version_id": first_version.version_id}
            ),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        # check if we just update this then before and after are confusing
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        first_version.not_active_after = now_utc() + relativedelta(days=10)
        first_version.save()
        setup_dict["plan_version_update_payload"][
            "not_active_before"
        ] = now_utc() + relativedelta(days=3)
        response = setup_dict["client"].patch(
            reverse(
                "plan_version-detail", kwargs={"version_id": first_version.version_id}
            ),
            data=json.dumps(
                setup_dict["plan_version_update_payload"], cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        listed_plan = (
            setup_dict["client"]
            .get(
                reverse("plan-list")
                + "?"
                + urllib.parse.urlencode({"active_on": now_utc().isoformat()})
            )
            .data[0]
        )
        assert len(listed_plan["versions"]) == 0
