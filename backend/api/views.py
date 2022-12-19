# Create your views here.
import base64
import copy
import datetime
import json
import logging
import operator
from datetime import timezone
from functools import reduce
from typing import Dict, Union

import lotus_python
import posthog
from actstream import action
from api.serializers.model_serializers import *
from api.serializers.nonmodel_serializers import (
    GetCustomerEventAccessRequestSerializer,
    GetCustomerFeatureAccessRequestSerializer,
    GetEventAccessSerializer,
    GetFeatureAccessSerializer,
)
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch, Q
from django.db.utils import IntegrityError
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth.auth_utils import fast_api_key_validation_and_cache
from metering_billing.exceptions import (
    DuplicateCustomer,
    MethodNotAllowed,
    NotFoundException,
    SwitchPlanDurationMismatch,
    SwitchPlanSamePlanException,
)
from metering_billing.exceptions.exceptions import NotFoundException
from metering_billing.invoice import generate_invoice
from metering_billing.kafka.producer import Producer
from metering_billing.models import (
    APIToken,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    Invoice,
    Plan,
    PlanComponent,
    PriceTier,
    SubscriptionRecord,
)
from metering_billing.permissions import HasUserAPIKey, ValidOrganization
from metering_billing.serializers.model_serializers import *
from metering_billing.utils import date_as_max_dt, now_utc
from metering_billing.utils.enums import (
    INVOICE_STATUS,
    PLAN_STATUS,
    SUBSCRIPTION_STATUS,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from svix.api import MessageIn, Svix

POSTHOG_PERSON = settings.POSTHOG_PERSON
SVIX_CONNECTOR = settings.SVIX_CONNECTOR


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


class CustomerViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Customers.
    """

    lookup_field = "customer_id"
    http_method_names = ["get", "post", "head"]
    queryset = Customer.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        qs = Customer.objects.filter(organization=organization).prefetch_related(
            "subscription_records",
            "invoices",
            "default_currency",
        )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return CustomerCreateSerializer
        return CustomerSerializer

    @extend_schema(
        responses={200: CustomerSerializer()},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        try:
            serializer.save(organization=self.request.organization)
        except IntegrityError as e:
            cause = e.__cause__
            if "unique_email" in str(cause):
                raise DuplicateCustomer("Customer email already exists")
            elif "unique_customer_id" in str(cause):
                raise DuplicateCustomer("Customer ID already exists")
            raise ServerError("Unknown error: " + str(cause))

    def get_serializer_context(self):
        context = super(CustomerViewSet, self).get_serializer_context()
        context.update({"organization": self.request.organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization or self.request.user.organization
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


class PlanViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

    serializer_class = PlanSerializer
    lookup_field = "plan_id"
    http_method_names = ["get", "head"]
    queryset = Plan.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        qs = Plan.objects.filter(organization=organization, status=PLAN_STATUS.ACTIVE)
        return qs

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization
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

    def get_serializer_context(self):
        context = super(PlanViewSet, self).get_serializer_context()
        organization = self.request.organization
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        context.update({"organization": organization, "user": user})
        return context


class SubscriptionViewSet(
    PermissionPolicyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    http_method_names = [
        "get",
        "head",
        "post",
    ]
    queryset = SubscriptionRecord.objects.all()

    def get_serializer_context(self):
        context = super(SubscriptionViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def get_serializer_class(self):
        if self.action == "edit":
            return SubscriptionRecordUpdateSerializer
        elif self.action == "cancel":
            return SubscriptionRecordCancelSerializer
        elif self.action == "create":
            return SubscriptionRecordCreateSerializer
        else:
            return SubscriptionRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        organization = self.request.organization
        qs = qs.filter(organization=organization)
        # need for: list, update_plans, cancel_plans
        if self.action == "list":
            args = []
            serializer = ListSubscriptionRecordFilter(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            allowed_status = serializer.validated_data.get("status")
            if len(allowed_status) == 0:
                allowed_status = [SUBSCRIPTION_STATUS.ACTIVE]
            range_start = serializer.validated_data.get("range_start")
            range_end = serializer.validated_data.get("range_end")
            if range_start:
                args.append(Q(end_date__gte=range_start))
            if range_end:
                args.append(Q(start_date__lte=range_end))
            range_end = serializer.validated_data.get("range_end")
            if serializer.validated_data.get("customer"):
                args.append(
                    Q(customer__customer_id=serializer.validated_data["customer"])
                )
            status_combo = []
            for status in allowed_status:
                status_combo.append(Q(status=status))
            args.append(reduce(operator.or_, status_combo))
            qs = qs.filter(
                *args,
            ).select_related("customer")
        elif self.action in ["edit", "cancel"]:
            params = self.request.query_params.copy()
            dict_params = params.dict()
            raw_filters = params.pop("subscription_filters", None)
            if raw_filters:
                if isinstance(raw_filters, list):
                    raw_filters = raw_filters[0]
                parsed_params = json.loads(raw_filters)
                dict_params["subscription_filters"] = parsed_params
            if self.action == "edit":
                serializer = SubscriptionRecordFilterSerializer(data=dict_params)
            elif self.action == "cancel":
                serializer = SubscriptionRecordFilterSerializerDelete(data=dict_params)
            else:
                raise Exception("Invalid action")
            serializer.is_valid(raise_exception=True)
            args = []
            args.append(Q(status=SUBSCRIPTION_STATUS.ACTIVE))
            args.append(Q(customer=serializer.validated_data["customer"]))
            if serializer.validated_data.get("plan_id"):
                args.append(Q(billing_plan__plan=serializer.validated_data["plan"]))
            organization = self.request.organization
            args.append(Q(organization=organization))
            qs = (
                SubscriptionRecord.objects.filter(*args)
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

            if serializer.validated_data.get("subscription_filters"):
                for filter in serializer.validated_data["subscription_filters"]:
                    m2m, _ = CategoricalFilter.objects.get_or_create(
                        property_name=filter["property_name"],
                        comparison_value=[filter["value"]],
                        operator=CATEGORICAL_FILTER_OPERATORS.ISIN,
                    )
                    qs = qs.filter(filters=m2m)
        return qs

    @extend_schema(
        parameters=[ListSubscriptionRecordFilter],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "Cannot use the create method on the subscription endpoint. Please use the /susbcriptions/add endpoint to attach a plan and create a subscription."
        )

    # ad hoc methods
    @extend_schema(responses=SubscriptionRecordSerializer)
    @action(detail=False, methods=["post"])
    def add(self, request, *args, **kwargs):
        # run checks to make sure it's valid
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # check to see if subscription exists
        subscription = (
            Subscription.objects.active()
            .filter(
                organization=organization,
                customer=serializer.validated_data["customer"],
            )
            .first()
        )
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
                months_btwn = relativedelta(end_date, tentative_nbd).months
                if months_btwn % num_months == 0:
                    found = True
                else:
                    i += 1
            serializer.validated_data[
                "next_billing_date"
            ] = tentative_nbd  # end_date - i * relativedelta(months=num_months)
        subscription_record = serializer.save(
            organization=organization, status="active"
        )

        # now we can actually create the subscription record
        response = self.get_serializer(subscription_record).data
        return Response(
            response,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            SubscriptionRecordFilterSerializerDelete,
        ],
        responses={200: SubscriptionRecordSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        qs = self.get_queryset()
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        usage_behavior = serializer.validated_data["usage_behavior"]
        invoicing_behavior = serializer.validated_data["invoicing_behavior"]

        now = now_utc()
        qs_pks = list(qs.values_list("pk", flat=True))
        qs.update(
            flat_fee_behavior=flat_fee_behavior,
            invoice_usage_charges=usage_behavior == USAGE_BILLING_BEHAVIOR.BILL_FULL,
            auto_renew=False,
            end_date=now,
            status=SUBSCRIPTION_STATUS.ENDED,
            fully_billed=invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
        )
        qs = SubscriptionRecord.objects.filter(pk__in=qs_pks, organization=organization)
        customer_ids = qs.values_list("customer", flat=True).distinct()
        customer_set = Customer.objects.filter(
            id__in=customer_ids, organization=organization
        )
        if invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
            for customer in customer_set:
                subscription = (
                    Subscription.objects.active()
                    .filter(
                        organization=customer.organization,
                        customer=customer,
                    )
                    .first()
                )
                generate_invoice(subscription, qs.filter(customer=customer))
                subscription.handle_remove_plan()

        return_qs = SubscriptionRecord.objects.filter(
            pk__in=original_qs, organization=organization
        )
        ret = SubscriptionRecordSerializer(return_qs, many=True).data
        return Response(ret, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[SubscriptionRecordFilterSerializer],
        responses={200: SubscriptionRecordSerializer(many=True)},
    )
    @action(detail=False, methods=["post"], url_path="update")
    def edit(self, request, *args, **kwargs):
        qs = self.get_queryset()
        organization = self.request.organization
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        if qs.count() == 0:
            raise NotFoundException("Subscription matching the given filters not found")
        plan_to_replace = qs.first().billing_plan
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replace_billing_plan = serializer.validated_data.get("billing_plan")
        if replace_billing_plan:
            if replace_billing_plan == plan_to_replace:
                raise SwitchPlanSamePlanException("Cannot switch to the same plan")
            elif (
                replace_billing_plan.plan.plan_duration
                != plan_to_replace.plan.plan_duration
            ):
                raise SwitchPlanDurationMismatch(
                    "Cannot switch to a plan with a different duration"
                )
        billing_behavior = serializer.validated_data.get("invoicing_behavior")
        usage_behavior = serializer.validated_data.get("usage_behavior")
        turn_off_auto_renew = serializer.validated_data.get("turn_off_auto_renew")
        end_date = serializer.validated_data.get("end_date")
        if replace_billing_plan:
            now = now_utc()
            keep_separate = usage_behavior == USAGE_BEHAVIOR.KEEP_SEPARATE
            for subscription_record in qs:
                sr = SubscriptionRecord.objects.create(
                    organization=subscription_record.organization,
                    customer=subscription_record.customer,
                    billing_plan=replace_billing_plan,
                    start_date=now,
                    end_date=subscription_record.end_date,
                    next_billing_date=subscription_record.next_billing_date,
                    last_billing_date=subscription_record.last_billing_date,
                    usage_start_date=now
                    if keep_separate
                    else subscription_record.usage_start_date,
                    status=SUBSCRIPTION_STATUS.ACTIVE,
                    auto_renew=subscription_record.auto_renew,
                    fully_billed=False,
                    unadjusted_duration_seconds=subscription_record.unadjusted_duration_seconds,
                )
                for filter in subscription_record.filters.all():
                    sr.filters.add(filter)
                subscription_record.flat_fee_behavior = FLAT_FEE_BEHAVIOR.PRORATE
                subscription_record.invoice_usage_charges = keep_separate
                subscription_record.auto_renew = False
                subscription_record.end_date = now
                subscription_record.status = SUBSCRIPTION_STATUS.ENDED
                subscription_record.fully_billed = (
                    billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW
                )
                subscription_record.save()
            customer = list(qs)[0].customer
            subscription = (
                Subscription.objects.active()
                .filter(
                    organization=customer.organization,
                    customer=customer,
                )
                .first()
            )
            new_qs = SubscriptionRecord.objects.filter(
                pk__in=original_qs, organization=organization
            )
            if billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
                generate_invoice(subscription, new_qs)
        else:
            update_dict = {}
            if turn_off_auto_renew:
                update_dict["auto_renew"] = False
            if end_date:
                update_dict["end_date"] = end_date
                update_dict["next_billing_date"] = end_date
            if len(update_dict) > 0:
                qs.update(**update_dict)

        return_qs = SubscriptionRecord.objects.filter(
            pk__in=original_qs, organization=organization
        )
        ret = SubscriptionRecordSerializer(return_qs, many=True).data
        return Response(ret, status=status.HTTP_200_OK)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization
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


class InvoiceViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Invoices.
    """

    serializer_class = InvoiceSerializer
    http_method_names = ["get", "patch", "head"]
    lookup_field = "invoice_number"
    queryset = Invoice.objects.all()
    permission_classes_per_method = {
        "partial_update": [IsAuthenticated & ValidOrganization],
    }

    def get_queryset(self):
        args = [
            ~Q(payment_status=INVOICE_STATUS.DRAFT),
            Q(organization=self.request.organization),
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
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization
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

    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "delete", "head"]
    serializer_class = CustomerBalanceAdjustmentSerializer
    permission_classes_per_method = {
        "list": [IsAuthenticated & ValidOrganization],
        "create": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
    }
    lookup_field = "adjustment_id"
    queryset = CustomerBalanceAdjustment.objects.all()

    def get_queryset(self):
        filter_kwargs = {"organization": self.request.organization}
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            filter_kwargs["customer__customer_id"] = customer_id
        return CustomerBalanceAdjustment.objects.filter(**filter_kwargs)

    def get_serializer_context(self):
        context = super(CustomerBalanceAdjustmentViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

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


class GetCustomerEventAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[GetCustomerEventAccessRequestSerializer],
        responses={
            200: GetEventAccessSerializer(many=True),
        },
    )
    def get(self, request, format=None):
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerEventAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        # try:
        #     username = self.request.user.username
        # except:
        #     username = None
        # posthog.capture(
        #     POSTHOG_PERSON
        #     if POSTHOG_PERSON
        #     else (username if username else organization.company_name + " (Unknown)"),
        #     event="get_access",
        #     properties={"organization": organization.company_name},
        # )
        customer = serializer.validated_data["customer"]
        event_name = serializer.validated_data.get("event_name")
        access_metric = serializer.validated_data.get("metric")
        subscriptions = SubscriptionRecord.objects.select_related(
            "billing_plan"
        ).filter(
            organization_id=organization_pk,
            status=SUBSCRIPTION_STATUS.ACTIVE,
            customer=customer,
        )
        subscription_filters = {
            x["property_name"]: x["value"]
            for x in serializer.validated_data.get("subscription_filters", [])
        }
        for key, value in subscription_filters.items():
            key = f"properties__{key}"
            subscriptions = subscriptions.filter(**{key: value})
        metrics = []
        subscriptions = subscriptions.prefetch_related(
            "billing_plan__plan_components",
            "billing_plan__plan_components__billable_metric",
            "billing_plan__plan_components__tiers",
            "filters",
        )
        for sub in subscriptions:
            subscription_filters = {}
            for filter in sub.filters.all():
                subscription_filters[filter.property_name] = filter.comparison_value[0]
            single_sub_dict = {
                "plan_id": sub.billing_plan.plan_id,
                "subscription_filters": subscription_filters,
                "usage_per_component": [],
            }
            for component in sub.billing_plan.plan_components.all():
                metric = component.billable_metric
                if metric.event_name == event_name or access_metric == metric:
                    metric_name = metric.billable_metric_name
                    tiers = sorted(component.tiers.all(), key=lambda x: x.range_start)
                    free_limit = (
                        tiers[0].range_end
                        if tiers[0].type == PRICE_TIER_TYPE.FREE
                        else None
                    )
                    total_limit = tiers[-1].range_end
                    metric_usage = metric.get_current_usage(sub)
                    if metric_usage == {}:
                        unique_tup_dict = {
                            "event_name": metric.event_name,
                            "metric_name": metric_name,
                            "metric_usage": 0,
                            "metric_free_limit": free_limit,
                            "metric_total_limit": total_limit,
                            "metric_id": metric.metric_id,
                        }
                        single_sub_dict["usage_per_component"].append(unique_tup_dict)
                        continue
                    custom_metric_usage = metric_usage[customer.customer_name]
                    for unique_tup, d in custom_metric_usage.items():
                        i = iter(unique_tup)
                        try:
                            _ = next(i)  # i.next() in older versions
                            groupby_vals = list(i)
                        except:
                            groupby_vals = []
                        usage = list(d.values())[0]
                        unique_tup_dict = {
                            "event_name": metric.event_name,
                            "metric_name": metric_name,
                            "metric_usage": usage,
                            "metric_free_limit": free_limit,
                            "metric_total_limit": total_limit,
                            "metric_id": metric.metric_id,
                        }
                        if len(groupby_vals) > 0:
                            unique_tup_dict["separate_by_properties"] = dict(
                                zip(component.separate_by, groupby_vals)
                            )
                        single_sub_dict["usage_per_component"].append(unique_tup_dict)
            metrics.append(single_sub_dict)
        GetEventAccessSerializer(many=True).validate(metrics)
        return Response(
            metrics,
            status=status.HTTP_200_OK,
        )


class GetCustomerFeatureAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[GetCustomerFeatureAccessRequestSerializer],
        responses={
            200: GetFeatureAccessSerializer(many=True),
        },
    )
    def get(self, request, format=None):
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerFeatureAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        # try:
        #     username = self.request.user.username
        # except:
        #     username = None
        # posthog.capture(
        #     POSTHOG_PERSON
        #     if POSTHOG_PERSON
        #     else (username if username else organization.company_name + " (Unknown)"),
        #     event="get_access",
        #     properties={"organization": organization.company_name},
        # )
        customer = serializer.validated_data["customer"]
        feature_name = serializer.validated_data.get("feature_name")
        subscriptions = SubscriptionRecord.objects.select_related(
            "billing_plan"
        ).filter(
            organization_id=organization_pk,
            status=SUBSCRIPTION_STATUS.ACTIVE,
            customer=customer,
        )
        subscription_filters = {
            x["property_name"]: x["value"]
            for x in serializer.validated_data.get("subscription_filters", [])
        }
        for key, value in subscription_filters.items():
            key = f"properties__{key}"
            subscriptions = subscriptions.filter(**{key: value})
        features = []
        subscriptions = subscriptions.prefetch_related("billing_plan__features")
        for sub in subscriptions:
            subscription_filters = {}
            for filter in sub.filters.all():
                subscription_filters[filter.property_name] = filter.comparison_value[0]
            sub_dict = {
                "feature_name": feature_name,
                "plan_id": sub.billing_plan.plan_id,
                "subscription_filters": subscription_filters,
                "access": False,
            }
            for feature in sub.billing_plan.features.all():
                if feature.feature_name == feature_name:
                    sub_dict["access"] = True
            features.append(sub_dict)
        GetFeatureAccessSerializer(many=True).validate(features)
        return Response(
            features,
            status=status.HTTP_200_OK,
        )


class CustomerBatchCreateView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=inline_serializer(
            name="CustomerBatchCreateRequest",
            fields={
                "customers": CustomerSerializer(many=True),
                "behavior_on_existing": serializers.ChoiceField(
                    choices=["merge", "ignore", "overwrite"]
                ),
            },
        ),
        responses={
            201: inline_serializer(
                name="CustomerBatchCreateSuccess",
                fields={
                    "success": serializers.ChoiceField(choices=["all", "some"]),
                    "failed_customers": serializers.DictField(required=False),
                },
            ),
            400: inline_serializer(
                name="CustomerBatchCreateFailure",
                fields={
                    "success": serializers.ChoiceField(choices=["none"]),
                    "failed_customers": serializers.DictField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = request.organization
        serializer = CustomerSerializer(
            data=request.data["customers"],
            many=True,
            context={"organization": organization},
        )
        serializer.is_valid(raise_exception=True)
        failed_customers = {}
        behavior = request.data.get("behavior_on_existing", "merge")
        for customer in serializer.validated_data:
            try:
                match = Customer.objects.filter(
                    Q(email=customer["email"]) | Q(customer_id=customer["customer_id"]),
                    organization=organization,
                )
                if match.exists():
                    match = match.first()
                    if behavior == "ignore":
                        pass
                    else:
                        if "customer_id" in customer:
                            non_unique_id = Customer.objects.filter(
                                ~Q(pk=match.pk), customer_id=customer["customer_id"]
                            ).exists()
                            if non_unique_id:
                                failed_customers[
                                    customer["customer_id"]
                                ] = "customer_id already exists"
                                continue
                        CustomerSerializer().update(match, customer, behavior=behavior)
                else:
                    customer["organization"] = organization
                    CustomerSerializer().create(customer)
            except Exception as e:
                identifier = customer.get("customer_id", customer.get("email"))
                failed_customers[identifier] = str(e)

        if len(failed_customers) == 0 or len(failed_customers) < len(
            serializer.validated_data
        ):
            return Response(
                {
                    "success": "all" if len(failed_customers) == 0 else "some",
                    "failed_customers": failed_customers,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {
                "success": "none",
                "failed_customers": failed_customers,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ConfirmIdemsReceivedView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=inline_serializer(
            name="ConfirmIdemsReceivedRequest",
            fields={
                "idempotency_ids": serializers.ListField(
                    child=serializers.CharField(), required=True
                ),
                "number_days_lookback": serializers.IntegerField(
                    default=30, required=False
                ),
                "customer_id": serializers.CharField(required=False),
            },
        ),
        responses={
            200: inline_serializer(
                name="ConfirmIdemsReceived",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "ids_not_found": serializers.ListField(
                        child=serializers.CharField(), required=True
                    ),
                },
            ),
            400: inline_serializer(
                name="ConfirmIdemsReceivedFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["failure"]),
                    "error": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = request.organization
        if request.data.get("idempotency_ids") is None:
            return Response(
                {
                    "status": "failure",
                    "error": "idempotency_ids is required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(request.data.get("idempotency_ids"), str):
            idempotency_ids = {request.data.get("idempotency_ids")}
        else:
            idempotency_ids = list(set(request.data.get("idempotency_ids")))
        number_days_lookback = request.data.get("number_days_lookback", 30)
        now_minus_lookback = now_utc() - relativedelta(days=number_days_lookback)
        num_batches_idems = len(idempotency_ids) // 1000 + 1
        ids_not_found = []
        for i in range(num_batches_idems):
            idem_batch = set(idempotency_ids[i * 1000 : (i + 1) * 1000])
            events = Event.objects.filter(
                organization=organization,
                time_created__gte=now_minus_lookback,
                idempotency_id__in=idem_batch,
            )
            if request.data.get("customer_id"):
                events = events.filter(customer_id=request.data.get("customer_id"))
            events_set = set(events.values_list("idempotency_id", flat=True))
            ids_not_found += list(idem_batch - events_set)
        return Response(
            {
                "status": "success",
                "ids_not_found": ids_not_found,
            },
            status=status.HTTP_200_OK,
        )


logger = logging.getLogger("app_api")  # from LOGGING.loggers in settings.py
kafka_producer = Producer()


def load_event(request: HttpRequest) -> Union[None, Dict]:
    """
    Loads an event from the request body.
    """
    if request.content_type == "application/json":
        try:
            event_data = json.loads(request.body)
            return event_data
        except json.JSONDecodeError as e:
            print(e)
            # if not, it's probably base64 encoded from other libraries
            event_data = json.loads(
                base64.b64decode(request + "===")
                .decode("utf8", "surrogatepass")
                .encode("utf-16", "surrogatepass")
            )
    else:
        event_data = request.body.decode("utf8")

    return event_data


def ingest_event(data: dict, customer_id: str, organization_pk: int) -> None:
    event_kwargs = {
        "organization_id": organization_pk,
        "cust_id": customer_id,
        "event_name": data["event_name"],
        "idempotency_id": data["idempotency_id"],
        "time_created": data["time_created"],
        "properties": {},
    }
    if "properties" in data:
        event_kwargs["properties"] = data["properties"]
    return event_kwargs


@csrf_exempt
@extend_schema(
    request=inline_serializer(
        "BatchEventSerializer", fields={"batch": EventSerializer(many=True)}
    ),
    responses={
        201: inline_serializer(
            name="TrackEventSuccess",
            fields={
                "success": serializers.ChoiceField(choices=["all", "some"]),
                "failed_events": serializers.DictField(),
            },
        ),
        400: inline_serializer(
            name="TrackEventFailure",
            fields={
                "success": serializers.ChoiceField(choices=["none"]),
                "failed_events": serializers.DictField(),
            },
        ),
    },
)
@api_view(http_method_names=["POST"])
@authentication_classes([])
@permission_classes([])
def track_event(request):
    result, success = fast_api_key_validation_and_cache(request)
    if not success:
        return result
    else:
        organization_pk = result

    try:
        event_list = load_event(request)
    except Exception as e:
        return HttpResponseBadRequest(f"Invalid event data: {e}")
    if not event_list:
        return HttpResponseBadRequest("No data provided")
    if type(event_list) != list:
        if "batch" in event_list:
            event_list = event_list["batch"]
        else:
            event_list = [event_list]

    bad_events = {}
    events_to_insert = set()
    events_by_customer = {}

    for data in event_list:
        customer_id = data.get("customer_id")
        idempotency_id = data.get("idempotency_id", None)
        if not customer_id or not idempotency_id:
            if not idempotency_id:
                bad_events["no_idempotency_id"] = "No idempotency_id provided"
            else:
                bad_events[idempotency_id] = "No customer_id provided"
            continue

        if idempotency_id in events_to_insert:
            bad_events[idempotency_id] = "Duplicate event idempotency in request"
            continue
        try:
            transformed_event = ingest_event(data, customer_id, organization_pk)
            events_to_insert.add(idempotency_id)
            if customer_id not in events_by_customer:
                events_by_customer[customer_id] = [transformed_event]
            else:
                events_by_customer[customer_id].append(transformed_event)
        except Exception as e:
            bad_events[idempotency_id] = str(e)
            continue

    ## Sent to Redpanda Topic
    for customer_id, events in events_by_customer.items():
        stream_events = {"events": events, "organization_id": organization_pk}
        kafka_producer.produce(customer_id, stream_events)

    if len(bad_events) == len(event_list):
        return Response(
            {"success": "none", "failed_events": bad_events},
            status=status.HTTP_400_BAD_REQUEST,
        )
    elif len(bad_events) > 0:
        return JsonResponse(
            {"success": "some", "failed_events": bad_events},
            status=status.HTTP_201_CREATED,
        )
    else:
        return JsonResponse({"success": "all"}, status=status.HTTP_201_CREATED)
