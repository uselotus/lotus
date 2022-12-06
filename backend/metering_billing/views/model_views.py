import lotus_python
import posthog
from actstream import action
from actstream.models import Action
from django.conf import settings
from django.db.models import Count, Prefetch, Q
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth import parse_organization
from metering_billing.exceptions import DuplicateCustomerID, DuplicateMetric
from metering_billing.models import (
    Backtest,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    Metric,
    OrganizationSetting,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceTier,
    PricingUnit,
    Product,
    SubscriptionRecord,
    User,
    WebhookEndpoint,
    WebhookTrigger,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.backtest_serializers import (
    BacktestCreateSerializer,
    BacktestDetailSerializer,
    BacktestSummarySerializer,
)
from metering_billing.serializers.model_serializers import *
from metering_billing.tasks import run_backtest
from metering_billing.utils import date_as_max_dt, now_utc, now_utc_ts
from metering_billing.utils.enums import (
    INVOICE_STATUS,
    METRIC_STATUS,
    PAYMENT_PROVIDERS,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from svix.api import MessageIn, Svix

POSTHOG_PERSON = settings.POSTHOG_PERSON
SVIX_API_KEY = settings.SVIX_API_KEY


class CustomPagination(CursorPagination):
    def get_paginated_response(self, data):
        if self.get_next_link():
            next_link = self.get_next_link()
            next_cursor = next_link[
                next_link.index(f"{self.cursor_query_param}=")
                + len(f"{self.cursor_query_param}=") :
            ]
        else:
            next_cursor = None
        if self.get_previous_link():
            previous_link = self.get_previous_link()
            previous_cursor = previous_link[
                previous_link.index(f"{self.cursor_query_param}=")
                + len(f"{self.cursor_query_param}=") :
            ]
        else:
            previous_cursor = None
        return Response(
            {
                "next": next_cursor,
                "previous": previous_cursor,
                "results": data,
            }
        )


class PermissionPolicyMixin:
    def check_permissions(self, request):
        try:
            # This line is heavily inspired from `APIView.dispatch`.
            # It returns the method associated with an endpoint.
            handler = getattr(self, request.method.lower())
        except AttributeError:
            handler = None

        try:
            if (
                handler
                and self.permission_classes_per_method
                and self.permission_classes_per_method.get(handler.__name__)
            ):
                self.permission_classes = self.permission_classes_per_method.get(
                    handler.__name__
                )
        except:
            pass

        super().check_permissions(request)


class WebhookViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows alerts to be viewed or edited.
    """

    serializer_class = WebhookEndpointSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "delete", "patch"]
    lookup_field = "webhook_endpoint_id"
    permission_classes_per_method = {
        "create": [IsAuthenticated],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "destroy": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return WebhookEndpoint.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(WebhookViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except ValueError as e:
            raise APIException(e)

    def perform_destroy(self, instance):
        if SVIX_API_KEY != "":
            svix = Svix(SVIX_API_KEY)
            svix.endpoint.delete(
                instance.organization.organization_id,
                instance.webhook_endpoint_id,
            )
        instance.delete()

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_webhook",
                properties={"organization": organization.company_name},
            )
        return response


class CursorSetPagination(CustomPagination):
    page_size = 10
    page_size_query_param = "page_size"
    ordering = "-time_created"
    cursor_query_param = "c"


class EventViewSet(
    PermissionPolicyMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    API endpoint that allows events to be viewed.
    """

    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_class = CursorSetPagination
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "head",
    ]

    def get_queryset(self):
        now = now_utc()
        organization = parse_organization(self.request)
        return (
            super()
            .get_queryset()
            .filter(organization=organization, time_created__lt=now)
        )

    def get_serializer_context(self):
        context = super(EventViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class UserViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Users.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return User.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(UserViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class CustomerViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Customers.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = "customer_id"
    http_method_names = ["get", "post", "head", "patch"]
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "partial_update": [IsAuthenticated | HasUserAPIKey],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = Customer.objects.filter(organization=organization)
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "subscription_records",
                    queryset=SubscriptionRecord.objects.filter(
                        organization=organization, status=SUBSCRIPTION_STATUS.ACTIVE
                    ),
                ),
                Prefetch(
                    "subscription_records__billing_plan",
                    queryset=PlanVersion.objects.filter(organization=organization),
                    to_attr="billing_plans",
                ),
            )
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CustomerDetailSerializer
        elif self.action == "partial_update":
            return CustomerUpdateSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateCustomerID

    def get_serializer_context(self):
        context = super(CustomerViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        if self.action == "retrieve":
            customer = self.get_object()
            total_amount_due = customer.get_outstanding_revenue()
            next_amount_due = customer.get_active_sub_drafts_revenue()
            invoices = Invoice.objects.filter(
                ~Q(payment_status=INVOICE_STATUS.DRAFT),
                organization=organization,
                customer=customer,
            ).order_by("-issue_date")
            context.update(
                {
                    "total_amount_due": total_amount_due,
                    "invoices": invoices,
                    "next_amount_due": next_amount_due,
                }
            )
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_customer",
                properties={"organization": organization.company_name},
            )
        return response


class MetricViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Billable Metrics.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "patch"]
    lookup_field = "metric_id"
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "partial_update": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Metric.objects.filter(
            organization=organization, status=METRIC_STATUS.ACTIVE
        )

    def get_serializer_class(self):
        if self.action == "partial_update":
            return MetricUpdateSerializer
        return MetricSerializer

    def get_serializer_context(self):
        context = super(MetricViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_metric",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_create(self, serializer):
        try:
            instance = serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateMetric
        # if self.request.user.is_authenticated:
        #     action.send(
        #         self.request.user,
        #         verb="created",
        #         action_object=instance,
        #     )


class FeatureViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Features.
    """

    serializer_class = FeatureSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head"]
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "destroy": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Feature.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(FeatureViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_feature",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class PlanVersionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing PlanVersions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    serializer_class = PlanVersionSerializer
    lookup_field = "version_id"
    http_method_names = [
        "post",
        "head",
        "patch",
    ]
    permission_classes_per_method = {
        "create": [IsAuthenticated | HasUserAPIKey],
        "partial_update": [IsAuthenticated],
    }

    def get_serializer_class(self):
        if self.action == "partial_update":
            return PlanVersionUpdateSerializer
        return PlanVersionSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = PlanVersion.objects.filter(
            organization=organization,
        )
        return qs

    def get_serializer_context(self):
        context = super(PlanVersionViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        context.update({"organization": organization, "user": user})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_plan_version",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        instance = serializer.save(
            organization=parse_organization(self.request), created_by=user
        )
        # if user:
        #     action.send(
        #         user,
        #         verb="created",
        #         action_object=instance,
        #         target=instance.plan,
        #     )

    def perform_update(self, serializer):
        instance = serializer.save()
        # if self.request.user.is_authenticated:
        #     user = self.request.user
        # else:
        #     user = None
        # if user:
        #     if instance.status == PLAN_VERSION_STATUS.ACTIVE:
        #         action.send(
        #             user,
        #             verb="activated",
        #             action_object=instance,
        #             target=instance.plan,
        #         )
        #     elif instance.status == PLAN_VERSION_STATUS.ARCHIVED:
        #         action.send(
        #             user,
        #             verb="archived",
        #             action_object=instance,
        #             target=instance.plan,
        #         )


class PlanViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "plan_id"
    http_method_names = ["get", "post", "patch", "head"]
    queryset = Plan.objects.all()
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = Plan.objects.filter(organization=organization, status=PLAN_STATUS.ACTIVE)
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "versions",
                    queryset=PlanVersion.objects.filter(
                        ~Q(status=PLAN_VERSION_STATUS.ARCHIVED),
                        organization=organization,
                    ).annotate(
                        active_subscriptions=Count(
                            "subscription_record",
                            filter=Q(
                                subscription_record__status=SUBSCRIPTION_STATUS.ACTIVE
                            ),
                        )
                    ),
                )
            )
        return qs

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_plan",
                properties={"organization": organization.company_name},
            )
        return response

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PlanDetailSerializer
        elif self.action == "partial_update":
            return PlanUpdateSerializer
        return PlanSerializer

    def get_serializer_context(self):
        context = super(PlanViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        context.update({"organization": organization, "user": user})
        return context

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        instance = serializer.save(
            organization=parse_organization(self.request), created_by=user
        )
        # if user:
        #     action.send(
        #         user,
        #         verb="created",
        #         action_object=instance,
        #     )

    def perform_update(self, serializer):
        instance = serializer.save()
        # if self.request.user.is_authenticated:
        #     user = self.request.user
        # else:
        #     user = None
        # if user and instance.status == PLAN_STATUS.ARCHIVED:
        #     action.send(
        #         user,
        #         verb="archived",
        #         action_object=instance,
        #     )


class SubscriptionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    http_method_names = ["get", "head", "patch", "post", "delete"]
    lookup_field = "subscription_id"
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "delete": [IsAuthenticated | HasUserAPIKey],
        "plans": [IsAuthenticated | HasUserAPIKey],
        "update_plans": [IsAuthenticated | HasUserAPIKey],
        "cancel_plans": [IsAuthenticated | HasUserAPIKey],
    }

    def get_serializer_context(self):
        context = super(SubscriptionViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def get_serializer_class(self):
        if self.action == "plans":
            return SubscriptionRecordSerializer
        elif self.action == "update_plans":
            return SubscriptionRecordUpdateSerializer
        elif self.action == "cancel_plans":
            return SubscriptionRecordCancelSerializer
        elif self.action == "delete":
            return SubscriptionCancelSerializer
        else:
            return SubscriptionSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        # need for: list, update_plans, cancel_plans
        if self.action == "list":
            args = []
            serializer = SubscriptionStatusFilterSerializer(self.request.query_params)
            serializer.is_valid(raise_exception=True)
            args.append(Q(status__in=serializer.validated_data["status"]))
            if serializer.validated_data.get("customer_id"):
                args.append(
                    Q(customer__customer_id=serializer.validated_data["customer_id"])
                )

            qs = (
                Subscription.objects.filter(
                    *args,
                    organization=organization,
                )
                .select_related("customer")
                .select_related("billing_plan")
                .prefetch_related(
                    Prefetch(
                        "billing_plan__plan_components",
                        queryset=PlanComponent.objects.all(),
                    )
                )
                .prefetch_related(
                    Prefetch(
                        "billing_plan__plan_components__tiers",
                        queryset=PriceTier.objects.all(),
                    )
                )
            )
        elif self.action in ["update_plans", "cancel_plans"]:
            serializer = SubscriptionRecordFilterSerializer(
                data=self.request.query_params
            )
            serializer.is_valid(raise_exception=True)
            args = []
            args.append(Q(status=SUBSCRIPTION_STATUS.ACTIVE))
            if serializer.validated_data.get("customer_id"):
                args.append(
                    Q(customer__customer_id=serializer.validated_data["customer_id"])
                )
            if serializer.validated_data.get("subscription_filters"):
                for filter in serializer.validated_data["subscription_filters"]:
                    property_name = filter["property_name"]
                    value = filter["value"]
                    has_key = Q(filters__has_key=property_name)
                    key_is_not_null = Q(**{f"filters__{property_name}__isnull": False})
                    key_equals = Q(**{f"filters__{property_name}": value})
                    args.extend([has_key, key_is_not_null, key_equals])
            if serializer.validated_data.get("plan_id"):
                args.append(
                    Q(billing_plan__plan__plan_id=serializer.validated_data["plan_id"])
                )
            organization = parse_organization(self.request)
            args.append(Q(organization=organization))
            qs = SubscriptionRecord.objects.filter(*args)
        else:
            qs = Subscription.objects.filter(organization=organization)
        return qs

    @extend_schema(
        parameters=[SubscriptionStatusFilterSerializer],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)

    @extend_schema(
        parameters=[SubscriptionCancelSerializer],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request)

    def perform_destroy(self, instance):
        serializer = self.get_serializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        bill_usage = serializer.validated_data["bill_usage"]
        subscription = instance
        customer = subscription.customer
        subscription_records = customer.subscription_records.filter(
            organization=subscription.organization,
            next_billing_date__range=(
                subscription.start_date,
                subscription.end_date,
            ),
            fully_billed=False,
        )
        now = now_utc()
        subscription_records.update(
            flat_fee_behavior=flat_fee_behavior,
            invoice_usage_charges=bill_usage,
            auto_renew=False,
            end_date=now,
            status=SUBSCRIPTION_STATUS.ENDED,
            fully_billed=True,
        )
        subscription.status = SUBSCRIPTION_STATUS.ENDED
        subscription.end_date = now
        subscription.save()
        generate_invoice(subscription, subscription_records)

    def create(self, request, *args, **kwargs):
        # not allowed to create subscriptions directly, return a 405
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        # not allowed to update subscriptions directly, return a 405
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    # ad hoc methods
    @action(detail=False, methods=["post"])
    def plans(self, request, *args, **kwargs):
        # run checks to make sure it's valid
        organization = parse_organization(self.request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_name = serializer.validated_data["billing_plan"].plan.plan_name

        # check to see if subscription exists
        subscription = Subscription.objects.filter(
            organization=organization,
            status__in=[SUBSCRIPTION_STATUS.ACTIVE],
            customer=serializer.validated_data["customer"],
        ).first()
        duration = serializer.validated_data["billing_plan"].plan.plan_duration
        billing_freq = serializer.validated_data["billing_plan"].usage_billing_frequency
        start_date = serializer.validated_data["start_date"]
        plan_day_anchor = serializer.validated_data["billing_plan"].day_anchor
        plan_month_anchor = serializer.validated_data["billing_plan"].month_anchor
        if subscription is None:
            subscription = Subscription.objects.create(
                organization=organization,
                customer=serializer.validated_data["customer"],
                start_date=start_date,
                end_date=start_date,
                status=SUBSCRIPTION_STATUS.ACTIVE,
            )
        subscription.handle_attach_plan(
            plan_day_anchor=plan_day_anchor,
            plan_month_anchor=plan_month_anchor,
            plan_start_date=start_date,
            plan_duration=duration,
            plan_billing_frequency=billing_freq,
        )
        day_anchor, month_anchor = subscription.get_anchors()
        end_date = calculate_end_date(
            duration,
            start_date,
            day_anchor=day_anchor,
            month_anchor=month_anchor,
        )
        end_date = serializer.validated_data.get("end_date", end_date)
        if billing_freq in [
            USAGE_BILLING_FREQUENCY.MONTHLY,
            USAGE_BILLING_FREQUENCY.QUARTERLY,
        ]:
            found = False
            i = 0
            num_months = 1 if billing_freq == USAGE_BILLING_FREQUENCY.MONTHLY else 3
            while not found:
                tentative_nbd = date_as_max_dt(
                    start_date + relativedelta(months=i, day=day_anchor, days=-1)
                )
                if tentative_nbd <= start_date:
                    i += 1
                    continue
                elif tentative_nbd > end_date:
                    tentative_nbd = end_date
                    break
                months_btwn = relativedelta(tentative_nbd, start_date).months
                if months_btwn % num_months == 0:
                    found = True
                else:
                    i += 1
            # next_billing_date = end_date + relativedelta(
            #     days=1, hour=0, minute=0, second=0, microsecond=0
            # )
            # done = False
            # i = 0
            # while not done:
            #     next_billing_date = end_date - i * relativedelta(months=num_months)
            #     if next_billing_date < now_utc() or next_billing_date < start_date:
            #         done = True
            #         i -= 1
            #     else:
            #         i += 1
            serializer.validated_data[
                "next_billing_date"
            ] = tentative_nbd  # end_date - i * relativedelta(months=num_months)
        subscription_record = serializer.save(organization=organization)

        # now we can actually create the subscription record
        response = self.get_serializer(subscription_record).data
        return Response(
            response,
            status=status.HTTP_201_CREATED,
        )

    @plans.mapping.delete
    @extend_schema(
        parameters=[
            SubscriptionRecordFilterSerializer,
            SubscriptionRecordCancelSerializer,
        ],
    )
    def cancel_plans(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        bill_usage = serializer.validated_data["bill_usage"]
        invoicing_behavior_on_cancel = serializer.validated_data[
            "invoicing_behavior_on_cancel"
        ]

        now = now_utc()
        qs_pks = list(qs.values_list("pk", flat=True))
        qs.update(
            flat_fee_behavior=flat_fee_behavior,
            invoice_usage_charges=bill_usage,
            auto_renew=False,
            end_date=now,
            status=SUBSCRIPTION_STATUS.ENDED,
            fully_billed=invoicing_behavior_on_cancel == INVOICING_BEHAVIOR.INVOICE_NOW,
        )
        qs = SubscriptionRecord.objects.filter(pk__in=qs_pks)
        customer_ids = qs.values_list("customer", flat=True).distinct()
        customer_set = Customer.objects.filter(id__in=customer_ids)
        if invoicing_behavior_on_cancel == INVOICING_BEHAVIOR.INVOICE_NOW:
            for customer in customer_set:
                subscription = Subscription.objects.filter(
                    organization=customer.organization,
                    customer=customer,
                    status=SUBSCRIPTION_STATUS.ACTIVE,
                ).first()
                generate_invoice(subscription, qs.filter(customer=customer))
                subscription.handle_remove_plan()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @plans.mapping.patch
    @extend_schema(
        parameters=[SubscriptionRecordFilterSerializer],
    )
    def update_plans(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replace_billing_plan = serializer.validated_data.get("billing_plan")
        replace_plan_billing_behavior = serializer.validated_data.get(
            "replace_plan_invoicing_behavior"
        )
        turn_off_auto_renew = serializer.validated_data.get("turn_off_auto_renew")
        end_date = serializer.validated_data.get("end_date")
        if replace_billing_plan:
            now = now_utc()
            for subscription_record in qs:
                sr = SubscriptionRecord.objects.create(
                    organization=subscription_record.organization,
                    customer=subscription_record.customer,
                    billing_plan=replace_billing_plan,
                    start_date=now,
                    end_date=subscription_record.end_date,
                    next_billing_date=subscription_record.next_billing_date,
                    last_billing_date=subscription_record.last_billing_date,
                    status=SUBSCRIPTION_STATUS.ACTIVE,
                    auto_renew=subscription_record.auto_renew,
                    fully_billed=False,
                    unadjusted_duration_days=subscription_record.unadjusted_duration_days,
                )
                for filter in subscription_record.filters.all():
                    sr.filters.add(filter)
            qs.update(
                flat_fee_behavior=FLAT_FEE_BEHAVIOR.PRORATE,
                invoice_usage_charges=False,
                auto_renew=False,
                end_date=now,
                status=SUBSCRIPTION_STATUS.ENDED,
                fully_billed=replace_plan_billing_behavior
                == INVOICING_BEHAVIOR.INVOICE_NOW,
            )
            customer_ids = qs.values_list("customer", flat=True).distinct()
            customer_set = Customer.objects.filter(id__in=customer_ids)
            if replace_plan_billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
                for customer in customer_set:
                    subscription = Subscription.objects.filter(
                        organization=customer.organization,
                        customer=customer,
                        status=SUBSCRIPTION_STATUS.ACTIVE,
                    ).first()
                    generate_invoice(subscription, qs.filter(customer=customer))
        else:
            if turn_off_auto_renew:
                qs.update(auto_renew=False)
            if end_date:
                qs.update(end_date=end_date, next_billing_date=end_date)

        return Response(status=status.HTTP_200_OK)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_subscription",
                properties={"organization": organization.company_name},
            )
            # if username:
            #     if self.action == "plans":
            #         action.send(
            #             self.request.user,
            #             verb="attached",
            #             action_object=instance.customer,
            #             target=instance.billing_plan,
            #         )

        return response


# def perform_create(self, serializer):
#     if serializer.validated_data["start_date"] <= now_utc():
#         serializer.validated_data["status"] = SUBSCRIPTION_STATUS.ACTIVE
#     instance = serializer.save(organization=parse_organization(self.request))

#     if self.request.user.is_authenticated:
#         action.send(
#             self.request.user,
#             verb="subscribed",
#             action_object=instance.customer,
#             target=instance.billing_plan,
#         )


class InvoiceViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Invoices.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head"]
    lookup_field = "invoice_id"
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "partial_update": [IsAuthenticated],
    }

    def get_queryset(self):
        args = [
            ~Q(payment_status=INVOICE_STATUS.DRAFT),
            Q(organization=parse_organization(self.request)),
        ]
        if self.action == "list":
            args = []
            serializer = InvoiceListFilterSerializer(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            args.append(
                Q(payment_status__in=serializer.validated_data["payment_status"])
            )
            if serializer.validated_data.get("customer_id"):
                args.append(
                    Q(customer__customer_id=serializer.validated_data["customer_id"])
                )

        return Invoice.objects.filter(*args)

    def get_serializer_class(self):
        if self.action == "partial_update":
            return InvoiceUpdateSerializer
        return InvoiceSerializer

    def get_serializer_context(self):
        context = super(InvoiceViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_invoice",
                properties={"organization": organization.company_name},
            )
        return response

    @extend_schema(
        parameters=[InvoiceListFilterSerializer],
    )
    def list(self, request):
        return super().list(request)


class BacktestViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Backtests.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "backtest_id"
    http_method_names = [
        "get",
        "post",
        "head",
    ]
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "destroy": [IsAuthenticated],
    }

    def get_serializer_class(self):
        if self.action == "list":
            return BacktestSummarySerializer
        elif self.action == "retrieve":
            return BacktestDetailSerializer
        else:
            return BacktestCreateSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Backtest.objects.filter(organization=organization)

    def perform_create(self, serializer):
        backtest_obj = serializer.save(organization=parse_organization(self.request))
        bt_id = backtest_obj.backtest_id
        run_backtest.delay(bt_id)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_backtest",
                properties={"organization": organization.company_name},
            )
        return response

    def get_serializer_context(self):
        context = super(BacktestViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class ProductViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "product_id"
    http_method_names = [
        "get",
        "post",
        "head",
    ]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Product.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_product",
                properties={"organization": organization.company_name},
            )
        return response

    def get_serializer_context(self):
        context = super(ProductViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class ActionCursorSetPagination(CursorSetPagination):
    ordering = "-timestamp"


class ActionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint that allows events to be viewed.
    """

    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    pagination_class = ActionCursorSetPagination
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "head",
    ]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return (
            super()
            .get_queryset()
            .filter(
                actor_object_id__in=list(
                    User.objects.filter(organization=organization).values_list(
                        "id", flat=True
                    )
                )
            )
        )


class ExternalPlanLinkViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing ExternalPlanLink.
    """

    serializer_class = ExternalPlanLinkSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "external_plan_id"
    http_method_names = ["post", "head", "delete"]

    def get_queryset(self):
        filter_kwargs = {"organization": parse_organization(self.request)}
        source = self.request.query_params.get("source")
        if source:
            filter_kwargs["source"] = source
        return ExternalPlanLink.objects.filter(**filter_kwargs)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_external_plan_link",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def get_serializer_context(self):
        context = super(ExternalPlanLinkViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    @extend_schema(
        parameters=[
            inline_serializer(
                name="SourceSerializer",
                fields={
                    "source": serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
                },
            ),
        ],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request)


class OrganizationSettingViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing OrganizationSettings.
    """

    serializer_class = OrganizationSettingSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "patch"]
    lookup_field = "setting_id"

    def get_queryset(self):
        filter_kwargs = {"organization": parse_organization(self.request)}
        setting_name = self.request.query_params.get("setting_name")
        if setting_name:
            filter_kwargs["setting_name"] = setting_name
        setting_group = self.request.query_params.get("setting_group")
        if setting_group:
            filter_kwargs["setting_group"] = setting_group
        return OrganizationSetting.objects.filter(**filter_kwargs)


class PricingUnitViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    A simple ViewSet for viewing and editing PricingUnits.
    """

    serializer_class = PricingUnitSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return PricingUnit.objects.filter(
            Q(organization=organization) | Q(organization__isnull=True)
        )

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def get_serializer_context(self):
        context = super(PricingUnitViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class OrganizationViewSet(
    PermissionPolicyMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    A simple ViewSet for viewing and editing OrganizationSettings.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head"]
    permission_classes_per_method = {
        "list": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
    }
    lookup_field = "organization_id"

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Organization.objects.filter(pk=organization.pk)

    def get_object(self):
        queryset = self.get_queryset()
        obj = queryset.first()
        return obj

    def get_serializer_class(self):
        if self.action == "partial_update":
            return OrganizationUpdateSerializer
        return OrganizationSerializer

    def get_serializer_context(self):
        context = super(OrganizationViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class CustomerBalanceAdjustmentViewSet(
    PermissionPolicyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    A simple ViewSet meant only for creating CustomerBalanceAdjustments.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head"]
    serializer_class = CustomerBalanceAdjustmentSerializer
    permission_classes_per_method = {
        "list": [IsAuthenticated],
        "create": [IsAuthenticated],
        "destroy": [IsAuthenticated],
    }
    lookup_field = "adjustment_id"

    def get_queryset(self):
        filter_kwargs = {"organization": parse_organization(self.request)}
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            filter_kwargs["customer__customer_id"] = customer_id
        return CustomerBalanceAdjustment.objects.filter(**filter_kwargs)

    def get_serializer_context(self):
        context = super(CustomerBalanceAdjustmentViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    @extend_schema(
        parameters=[
            inline_serializer(
                name="BalanceAdjustmentCustomerFilter",
                fields={
                    "customer_id": serializers.CharField(required=True),
                },
            ),
        ],
    )
    def list(self, request):
        return super().list(request)

    def perform_destroy(self, instance):
        if instance.amount <= 0:
            raise ValidationError("Cannot delete a negative adjustment.")
        instance.zero_out(reason="voided")
