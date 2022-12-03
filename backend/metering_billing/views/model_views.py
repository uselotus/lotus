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
from metering_billing.utils import now_utc, now_utc_ts
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


# class SubscriptionRecordViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
#     """
#     A simple ViewSet for viewing and editing Subscription Records.
#     """

#     serializer_class = SubscriptionRecordSerializer
#     permission_classes = [IsAuthenticated | HasUserAPIKey]
#     http_method_names = ["get", "post", "head", "patch", "delete"]
#     lookup_field = "plan_id"
#     permission_classes_per_method = {
#         "list": [IsAuthenticated | HasUserAPIKey],
#         "retrieve": [IsAuthenticated | HasUserAPIKey],
#         "create": [IsAuthenticated | HasUserAPIKey],
#         "partial_update": [IsAuthenticated | HasUserAPIKey],
#         "destroy": [IsAuthenticated | HasUserAPIKey],
#     }

#     def get_serializer_class(self):
#         if self.action == "partial_update":
#             return SubscriptionRecordUpdateSerializer
#         elif self.action == "retrieve":
#             return SubscriptionRecordDetailSerializer
#         else:
#             return SubscriptionRecordSerializer

#     def get_serializer_context(self):
#         context = super(SubscriptionRecordViewSet, self).get_serializer_context()
#         organization = parse_organization(self.request)
#         context.update({"organization": organization})
#         return context

#     def get_queryset(self):
#         try:
#             if self.action == "list":
#                 args = []
#                 serializer = SubscriptionListFilterSerializer(
#                     self.request.query_params
#                 ).is_valid(raise_exception=True)
#                 args.append(Q(status__in=serializer.validated_data["status"]))
#                 if serializer.validated_data.get("plan_id"):
#                     args.append(
#                         Q(
#                             billing_plan__plan__plan_id=serializer.validated_data[
#                                 "plan_id"
#                             ]
#                         )
#                     )
#             else:
#                 args = [Q(status__in=[SUBSCRIPTION_STATUS.ACTIVE])]
#             has_customer = self.kwargs.get("customer_customer_id")
#             if has_customer:
#                 args.append(Q(customer__customer_id=has_customer))
#             organization = parse_organization(self.request)
#             qs = (
#                 SubscriptionRecord.objects.filter(
#                     *args,
#                     organization=organization,
#                 )
#                 .select_related("customer")
#                 .select_related("billing_plan")
#             )
#             if self.action == "retrieve":
#                 qs = qs.prefetch_related(
#                     Prefetch(
#                         "billing_plan__plan_components",
#                         queryset=PlanComponent.objects.all(),
#                     )
#                 ).prefetch_related(
#                     Prefetch(
#                         "billing_plan__plan_components__tiers",
#                         queryset=PriceTier.objects.all(),
#                     )
#                 )
#         except Exception as e:
#             print("error is:", e)
#             raise

#         return qs

#     def perform_create(self, serializer):
#         if serializer.validated_data["start_date"] <= now_utc():
#             serializer.validated_data["status"] = SUBSCRIPTION_STATUS.ACTIVE
#         instance = serializer.save(organization=parse_organization(self.request))

#         if self.request.user.is_authenticated:
#             action.send(
#                 self.request.user,
#                 verb="subscribed",
#                 action_object=instance.customer,
#                 target=instance.billing_plan,
#             )

#     @extend_schema(
#         parameters=[SubscriptionRecordFilterSerializer],
#     )
#     def list(self, request, *args, **kwargs):
#         return super().list(request)

#     @extend_schema(
#         parameters=[SubscriptionRecordDeleteSerializer],
#     )
#     def destroy(self, request, *args, **kwargs):
#         return super().destroy(request)

#     def perform_destroy(self, instance):
#         serializer = SubscriptionCancelRequestSerializer(
#             self.request.query_params
#         ).is_valid(raise_exception=True)
#         flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
#         bill_usage = serializer.validated_data["bill_usage"]
#         instance.end_subscription_now(
#             flat_fee_behavior=flat_fee_behavior, bill_usage=bill_usage
#         )

#     def dispatch(self, request, *args, **kwargs):
#         response = super().dispatch(request, *args, **kwargs)
#         if status.is_success(response.status_code):
#             try:
#                 username = self.request.user.username
#             except:
#                 username = None
#             organization = parse_organization(self.request)
#             posthog.capture(
#                 POSTHOG_PERSON
#                 if POSTHOG_PERSON
#                 else (
#                     username if username else organization.company_name + " (API Key)"
#                 ),
#                 event=f"{self.action}_subscription",
#                 properties={"organization": organization.company_name},
#             )
#         return response

#     def perform_update(self, serializer):
#         instance = serializer.save()
#         if self.request.user.is_authenticated:
#             user = self.request.user
#         else:
#             user = None
#         if user:
#             if instance.status == SUBSCRIPTION_STATUS.ENDED:
#                 action.send(
#                     user,
#                     verb="canceled",
#                     action_object=instance.billing_plan,
#                     target=instance.customer,
#                 )
#             elif (
#                 serializer.validated_data.get("replace_immediately_type")
#                 == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
#             ):
#                 action.send(
#                     user,
#                     verb="switched to",
#                     action_object=instance.billing_plan,
#                     target=instance.customer,
#                 )


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
        if self.request.user.is_authenticated:
            action.send(
                self.request.user,
                verb="created",
                action_object=instance,
            )


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
        if user:
            action.send(
                user,
                verb="created",
                action_object=instance,
                target=instance.plan,
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        if user:
            if instance.status == PLAN_VERSION_STATUS.ACTIVE:
                action.send(
                    user,
                    verb="activated",
                    action_object=instance,
                    target=instance.plan,
                )
            elif instance.status == PLAN_VERSION_STATUS.ARCHIVED:
                action.send(
                    user,
                    verb="archived",
                    action_object=instance,
                    target=instance.plan,
                )


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
        if user:
            action.send(
                user,
                verb="created",
                action_object=instance,
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        if user and instance.status == PLAN_STATUS.ARCHIVED:
            action.send(
                user,
                verb="archived",
                action_object=instance,
            )


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

    def get_queryset(self):
        if self.action == "list":
            args = []
            serializer = SubscriptionListFilterSerializer(
                self.request.query_params
            ).is_valid(raise_exception=True)
            args.append(Q(status__in=serializer.validated_data["status"]))
            if serializer.validated_data.get("plan_id"):
                args.append(
                    Q(billing_plan__plan__plan_id=serializer.validated_data["plan_id"])
                )
            if serializer.validated_data.get("customer_id"):
                args.append(
                    Q(customer__customer_id=serializer.validated_data["customer_id"])
                )
        else:
            args = [Q(status__in=[SUBSCRIPTION_STATUS.ACTIVE])]
        organization = parse_organization(self.request)
        qs = (
            Subscription.objects.filter(
                *args,
                organization=organization,
            )
            .select_related("customer")
            .select_related("billing_plan")
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "billing_plan__plan_components",
                    queryset=PlanComponent.objects.all(),
                )
            ).prefetch_related(
                Prefetch(
                    "billing_plan__plan_components__tiers",
                    queryset=PriceTier.objects.all(),
                )
            )

        return qs

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

    @extend_schema(
        parameters=[SubscriptionRecordFilterSerializer],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)

    @extend_schema(
        parameters=[SubscriptionRecordDeleteSerializer],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request)

    def _perform_destroy(self, instance):
        serializer = SubscriptionRecordDeleteSerializer(
            self.request.query_params
        ).is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        bill_usage = serializer.validated_data["bill_usage"]
        instance.end_subscription_now(
            flat_fee_behavior=flat_fee_behavior, bill_usage=bill_usage
        )

    def get_serializer_class(self):
        if self.action == "plans":
            return SubscriptionRecordSerializer
        elif self.action == "update_plans":
            return SubscriptionRecordUpdateSerializer

        #     {
        #     "list": [IsAuthenticated | HasUserAPIKey],
        #     "retrieve": [IsAuthenticated | HasUserAPIKey],
        #     "partial_update": [IsAuthenticated | HasUserAPIKey],
        #     "delete": [IsAuthenticated | HasUserAPIKey],
        #     "plans": [IsAuthenticated | HasUserAPIKey],
        #     "update_plans": [IsAuthenticated | HasUserAPIKey],
        #     "cancel_plans": [IsAuthenticated | HasUserAPIKey],
        # }
        if self.action == "partial_update":
            return SubscriptionUpdateSerializer
        elif self.action == "retrieve":
            return SubscriptionDetailSerializer
        else:
            return SubscriptionSerializer

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
        return response

    def perform_update(self, serializer):
        instance = serializer.save()
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        if user:
            if instance.status == SUBSCRIPTION_STATUS.ENDED:
                action.send(
                    user,
                    verb="canceled",
                    action_object=instance.billing_plan,
                    target=instance.customer,
                )
            elif (
                serializer.validated_data.get("replace_immediately_type")
                == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
            ):
                action.send(
                    user,
                    verb="switched to",
                    action_object=instance.billing_plan,
                    target=instance.customer,
                )

    @action(detail=False, methods=["post"])
    def plans(self, request, *args, **kwargs):
        serializer = SubscriptionAddPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(self.request)
        subscription = Subscription.objects.filter(
            organization=organization,
            status__in=[SUBSCRIPTION_STATUS.ACTIVE, SUBSCRIPTION_STATUS.TRIAL],
        ).first()
        if not subscription:
            raise ValidationError("No active subscription found for this organization")
        billing_plan = serializer.validated_data["billing_plan"]
        subscription.add_plan(billing_plan)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @plans.mapping.delete
    @extend_schema(
        parameters=[
            SubscriptionRecordFilterSerializer,
            SubscriptionRecordDeleteSerializer,
        ],
    )
    def cancel_plans(self, request, *args, **kwargs):
        serializer = SubscriptionRemovePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(self.request)
        subscription = Subscription.objects.filter(
            organization=organization,
            status__in=[SUBSCRIPTION_STATUS.ACTIVE, SUBSCRIPTION_STATUS.TRIAL],
        ).first()
        if not subscription:
            raise ValidationError("No active subscription found for this organization")
        billing_plan = serializer.validated_data["billing_plan"]
        subscription.remove_plan(billing_plan)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @plans.mapping.patch
    @extend_schema(
        parameters=[SubscriptionRecordFilterSerializer],
    )
    def update_plans(self, request, *args, **kwargs):
        serializer = SubscriptionUpdatePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(self.request)
        subscription = Subscription.objects.filter(
            organization=organization,
            status__in=[SUBSCRIPTION_STATUS.ACTIVE, SUBSCRIPTION_STATUS.TRIAL],
        ).first()
        if not subscription:
            raise ValidationError("No active subscription found for this organization")
        billing_plan = serializer.validated_data["billing_plan"]
        subscription.update_plan(billing_plan)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
            serializer = InvoiceListFilterSerializer(
                self.request.query_params
            ).is_valid(raise_exception=True)
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
