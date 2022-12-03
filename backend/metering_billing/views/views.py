import datetime
from decimal import Decimal

import posthog
from dateutil import parser
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, Prefetch, Q, Sum
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth import parse_organization
from metering_billing.auth.auth_utils import fast_api_key_validation_and_cache
from metering_billing.invoice import generate_invoice
from metering_billing.models import APIToken, Customer, Metric, Subscription
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.auth_serializers import *
from metering_billing.serializers.backtest_serializers import *
from metering_billing.serializers.model_serializers import *
from metering_billing.serializers.request_serializers import *
from metering_billing.serializers.response_serializers import *
from metering_billing.utils import (
    convert_to_date,
    convert_to_decimal,
    date_as_max_dt,
    date_as_min_dt,
    make_all_dates_times_strings,
    make_all_decimals_floats,
    periods_bwn_twodates,
)
from metering_billing.utils.enums import (
    FLAT_FEE_BILLING_TYPE,
    PAYMENT_PROVIDERS,
    SUBSCRIPTION_STATUS,
    USAGE_CALC_GRANULARITY,
)
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

POSTHOG_PERSON = settings.POSTHOG_PERSON


class PeriodMetricRevenueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodMetricRevenueResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Returns the revenue for an organization in a given time period.
        """
        organization = parse_organization(request)
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = [
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        ]
        p1_start, p2_start = date_as_min_dt(p1_start), date_as_min_dt(p2_start)
        p1_end, p2_end = date_as_max_dt(p1_end), date_as_max_dt(p2_end)
        return_dict = {}
        # collected
        p1_collected = Invoice.objects.filter(
            organization=organization,
            issue_date__gte=p1_start,
            issue_date__lte=p1_end,
            payment_status=INVOICE_STATUS.PAID,
        ).aggregate(tot=Sum("cost_due"))["tot"]
        p2_collected = Invoice.objects.filter(
            organization=organization,
            issue_date__gte=p2_start,
            issue_date__lte=p2_end,
            payment_status=INVOICE_STATUS.PAID,
        ).aggregate(tot=Sum("cost_due"))["tot"]
        return_dict["total_revenue_period_1"] = p1_collected or Decimal(0)
        return_dict["total_revenue_period_2"] = p2_collected or Decimal(0)
        # earned
        for start, end, num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
            subs = (
                Subscription.objects.filter(
                    Q(start_date__range=(start, end))
                    | Q(end_date__range=(start, end))
                    | Q(start_date__lte=start, end_date__gte=end),
                    organization=organization,
                )
                .select_related("billing_plan")
                .select_related("customer")
                .prefetch_related("billing_plan__plan_components")
                .prefetch_related("billing_plan__plan_components__billable_metric")
                .prefetch_related("billing_plan__plan_components__tiers")
            )
            per_day_dict = {}
            for period in periods_bwn_twodates(
                USAGE_CALC_GRANULARITY.DAILY, start, end
            ):
                period = convert_to_date(period)
                per_day_dict[period] = {
                    "date": period,
                    "revenue": Decimal(0),
                }
            for subscription in subs:
                earned_revenue = subscription.calculate_earned_revenue_per_day()
                for date, earned_revenue in earned_revenue.items():
                    date = convert_to_date(date)
                    if date in per_day_dict:
                        per_day_dict[date]["revenue"] += earned_revenue
            return_dict[f"earned_revenue_period_{num}"] = sum(
                [x["revenue"] for x in per_day_dict.values()]
            )
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        ret = make_all_dates_times_strings(ret)
        return Response(ret, status=status.HTTP_200_OK)


class CostAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[CostAnalysisRequestSerializer],
        responses={200: CostAnalysisSerializer},
    )
    def get(self, request, format=None):
        """
        Returns the revenue for an organization in a given time period.
        """
        organization = parse_organization(request)
        serializer = CostAnalysisRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        start_date, end_date, customer_id = [
            serializer.validated_data.get(key, None)
            for key in ["start_date", "end_date", "customer_id"]
        ]
        try:
            customer = Customer.objects.get(
                organization=organization, customer_id=customer_id
            )
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        per_day_dict = {}
        for period in periods_bwn_twodates(
            USAGE_CALC_GRANULARITY.DAILY, start_date, end_date
        ):
            period = convert_to_date(period)
            per_day_dict[period] = {
                "date": period,
                "cost_data": {},
                "revenue": Decimal(0),
            }
        cost_metrics = Metric.objects.filter(
            organization=organization, is_cost_metric=True
        )
        for metric in cost_metrics:
            usage_ret = metric.get_usage(
                start_date,
                end_date,
                granularity=USAGE_CALC_GRANULARITY.DAILY,
                customer=customer,
            ).get(customer.customer_name, {})
            for unique_tup, unique_usage in usage_ret.items():
                for date, usage in unique_usage.items():
                    date = convert_to_date(date)
                    usage = convert_to_decimal(usage)
                    if date in per_day_dict:
                        if (
                            metric.billable_metric_name
                            not in per_day_dict[date]["cost_data"]
                        ):
                            per_day_dict[date]["cost_data"][
                                metric.billable_metric_name
                            ] = {
                                "metric": MetricSerializer(metric).data,
                                "cost": Decimal(0),
                            }
                        per_day_dict[date]["cost_data"][metric.billable_metric_name][
                            "cost"
                        ] += usage
        for date, items in per_day_dict.items():
            items["cost_data"] = [v for k, v in items["cost_data"].items()]
        subscriptions = (
            Subscription.objects.filter(
                Q(start_date__range=[start_date, end_date])
                | Q(end_date__range=[start_date, end_date])
                | (Q(start_date__lte=start_date) & Q(end_date__gte=end_date)),
                organization=organization,
                customer=customer,
            )
            .select_related("billing_plan")
            .select_related("customer")
            .prefetch_related("billing_plan__plan_components")
            .prefetch_related("billing_plan__plan_components__billable_metric")
            .prefetch_related("billing_plan__plan_components__tiers")
        )
        for subscription in subscriptions:
            earned_revenue = subscription.calculate_earned_revenue_per_day()
            for date, earned_revenue in earned_revenue.items():
                date = convert_to_date(date)
                if date in per_day_dict:
                    per_day_dict[date]["revenue"] += earned_revenue
        return_dict = {
            "per_day": [v for k, v in per_day_dict.items()],
        }
        total_cost = Decimal(0)
        for day in per_day_dict.values():
            for cost_data in day["cost_data"]:
                total_cost += convert_to_decimal(cost_data["cost"])
        total_revenue = Decimal(0)
        for day in per_day_dict.values():
            total_revenue += day["revenue"]
        return_dict["total_cost"] = total_cost
        return_dict["total_revenue"] = total_revenue
        if total_revenue == 0:
            return_dict["margin"] = 0
        else:
            return_dict["margin"] = convert_to_decimal(
                (total_revenue - total_cost) / total_revenue
            )
        serializer = CostAnalysisSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        ret = make_all_dates_times_strings(ret)
        return Response(ret, status=status.HTTP_200_OK)


class PeriodSubscriptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodSubscriptionsResponseSerializer},
    )
    def get(self, request, format=None):
        organization = parse_organization(request)
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = [
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        ]
        p1_start, p2_start = date_as_min_dt(p1_start), date_as_min_dt(p2_start)
        p1_end, p2_end = date_as_max_dt(p1_end), date_as_max_dt(p2_end)

        return_dict = {}
        for i, (p_start, p_end) in enumerate([[p1_start, p1_end], [p2_start, p2_end]]):
            p_subs = Subscription.objects.filter(
                Q(start_date__range=[p_start, p_end])
                | Q(end_date__range=[p_start, p_end]),
                organization=organization,
            ).values(customer_name=F("customer__customer_name"), new=F("is_new"))
            seen_dict = {}
            for sub in p_subs:
                if (
                    sub["customer_name"] in seen_dict
                ):  # seen before then they're def not new
                    seen_dict[sub["customer_name"]] = False
                else:
                    seen_dict[sub["customer_name"]] = sub["new"]
            return_dict[f"period_{i+1}_total_subscriptions"] = len(seen_dict)
            return_dict[f"period_{i+1}_new_subscriptions"] = sum(
                [1 for k, v in seen_dict.items() if v]
            )
        serializer = PeriodSubscriptionsResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        return Response(ret, status=status.HTTP_200_OK)


class PeriodMetricUsageView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodMetricUsageRequestSerializer],
        responses={200: PeriodMetricUsageResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        organization = parse_organization(request)
        serializer = PeriodMetricUsageRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        q_start, q_end, top_n = [
            serializer.validated_data.get(key, None)
            for key in ["start_date", "end_date", "top_n_customers"]
        ]
        if type(q_start) is str:
            q_start = parser.parse(q_start).date()
        if type(q_end) is str:
            q_end = parser.parse(q_end).date()
        q_start = date_as_min_dt(q_start)
        q_end = date_as_max_dt(q_end)

        metrics = Metric.objects.filter(organization=organization)
        return_dict = {}
        for metric in metrics:
            usage_summary = metric.get_usage(
                q_start,
                q_end,
                granularity=USAGE_CALC_GRANULARITY.DAILY,
            )
            return_dict[metric.billable_metric_name] = {
                "data": {},
                "total_usage": 0,
                "top_n_customers": {},
            }
            metric_dict = return_dict[metric.billable_metric_name]
            for customer_name, unique_dict in usage_summary.items():
                for unique_tuple, period_dict in unique_dict.items():
                    for time, qty in period_dict.items():
                        if qty is not None:
                            qty = convert_to_decimal(qty)
                        else:
                            qty = 0
                        customer_identifier = customer_name
                        if len(unique_tuple) > 1:
                            for unique in unique_tuple[1:]:
                                customer_identifier += f"__{unique}"
                        if time not in metric_dict["data"]:
                            metric_dict["data"][time] = {
                                "total_usage": Decimal(0),
                                "customer_usages": {},
                            }
                        date_dict = metric_dict["data"][time]
                        date_dict["total_usage"] += qty
                        date_dict["customer_usages"][customer_name] = qty
                        metric_dict["total_usage"] += qty
                        if customer_name not in metric_dict["top_n_customers"]:
                            metric_dict["top_n_customers"][customer_name] = 0
                        metric_dict["top_n_customers"][customer_name] += qty
            if top_n:
                top_n_customers = sorted(
                    metric_dict["top_n_customers"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:top_n]
                metric_dict["top_n_customers"] = [x[0] for x in top_n_customers]
                metric_dict["top_n_customers_usage"] = [x[1] for x in top_n_customers]
            else:
                del metric_dict["top_n_customers"]
        for metric, metric_d in return_dict.items():
            metric_d["data"] = [
                {
                    "date": str(k.date()),
                    "total_usage": v["total_usage"],
                    "customer_usages": v["customer_usages"],
                }
                for k, v in metric_d["data"].items()
            ]
            if metric_dict["top_n_customers"]:
                for date_dict in metric_d["data"]:
                    new_dict = {}
                    for customer, usage in date_dict["customer_usages"].items():
                        if customer not in metric_dict["top_n_customers"]:
                            if "Other" not in new_dict:
                                new_dict["Other"] = 0
                            new_dict["Other"] += usage
                        else:
                            new_dict[customer] = usage
                    date_dict["customer_usages"] = new_dict
            metric_d["data"] = sorted(metric_d["data"], key=lambda x: x["date"])
        return_dict = {"metrics": return_dict}
        serializer = PeriodMetricUsageResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        return Response(ret, status=status.HTTP_200_OK)


class APIKeyCreate(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="APIKeyCreateSuccess",
                fields={
                    "api_key": serializers.CharField(),
                },
            ),
        },
    )
    def get(self, request, format=None):
        """
        Revokes the current API key and returns a new one.
        """
        organization = parse_organization(request)
        tk = APIToken.objects.filter(organization=organization).first()
        if tk:
            cache.delete(tk.prefix)
            tk.delete()
        api_key, key = APIToken.objects.create_key(
            name="new_api_key", organization=organization
        )
        try:
            username = self.request.user.username
        except:
            username = None
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else (username if username else organization.company_name + " (Unknown)"),
            event="create_api_key",
            properties={"organization": organization.company_name},
        )
        return Response({"api_key": key}, status=status.HTTP_200_OK)


class SettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        return Response(
            {"organization": organization.company_name}, status=status.HTTP_200_OK
        )


class CustomersSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: CustomerSummarySerializer(many=True)},
    )
    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        customers = Customer.objects.filter(organization=organization).prefetch_related(
            Prefetch(
                "customer_subscriptions",
                queryset=Subscription.objects.filter(organization=organization),
                to_attr="subscriptions",
            ),
            Prefetch(
                "customer_subscriptions__billing_plan",
                queryset=PlanVersion.objects.filter(organization=organization),
                to_attr="billing_plans",
            ),
        )
        serializer = CustomerSummarySerializer(customers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomersWithRevenueView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: CustomerWithRevenueSerializer(many=True)},
    )
    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        organization = parse_organization(request)
        customers = Customer.objects.filter(organization=organization)
        cust = []
        for customer in customers:
            total_amount_due = customer.get_outstanding_revenue()
            next_amount_due = customer.get_active_sub_drafts_revenue()
            serializer = CustomerWithRevenueSerializer(
                customer,
                context={
                    "total_amount_due": total_amount_due,
                    "next_amount_due": next_amount_due,
                },
            )
            cust.append(serializer.data)
        cust = make_all_decimals_floats(cust)
        return Response(cust, status=status.HTTP_200_OK)


class DraftInvoiceView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[DraftInvoiceRequestSerializer],
        responses={200: DraftInvoiceSerializer(many=True)},
    )
    def get(self, request, format=None):
        """
        Pagination-enabled endpoint for retrieving an organization's event stream.
        """
        organization = parse_organization(request)
        serializer = DraftInvoiceRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            customer = Customer.objects.get(
                organization=organization,
                customer_id=serializer.validated_data.get("customer_id"),
            )
        except:
            return Response(
                {"error": "Customer not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subs = (
            Subscription.objects.filter(
                customer=customer,
                organization=organization,
                status=SUBSCRIPTION_STATUS.ACTIVE,
            )
            .select_related("billing_plan")
            .prefetch_related(
                "billing_plan__plan_components",
                "billing_plan__plan_components__billable_metric",
                "billing_plan__plan_components__tiers",
            )
        )
        invoices = [
            generate_invoice(sub, draft=True, charge_next_plan=True) for sub in subs
        ]
        serializer = DraftInvoiceSerializer(invoices, many=True).data
        try:
            username = self.request.user.username
        except:
            username = None
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else (username if username else organization.company_name + " (Unknown)"),
            event="draft_invoice",
            properties={"organization": organization.company_name},
        )
        for invoice in invoices:
            invoice.delete()
        return Response(serializer, status=status.HTTP_200_OK)


class GetCustomerAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[GetCustomerAccessRequestSerializer],
        responses={
            200: inline_serializer(
                name="GetCustomerAccessSuccess",
                fields={
                    "metrics": serializers.ListField(
                        child=inline_serializer(
                            name="MetricUsageSerializer",
                            fields={
                                "separate_by_properties": serializers.DictField(
                                    child=serializers.CharField()
                                ),
                                "event_name": serializers.CharField(),
                                "metric_name": serializers.CharField(),
                                "metric_usage": serializers.FloatField(),
                                "metric_free_limit": serializers.FloatField(),
                                "metric_total_limit": serializers.FloatField(),
                                "subscription_id": serializers.CharField(),
                            },
                        ),
                        required=False,
                    ),
                    "features": serializers.ListField(
                        child=inline_serializer(
                            name="FeatureUsageSerializer",
                            fields={
                                "feature_name": serializers.CharField(),
                                "subscription_id": serializers.CharField(),
                            },
                        ),
                        required=False,
                    ),
                },
            ),
            400: inline_serializer(
                name="GetCustomerAccessFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def get(self, request, format=None):
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerAccessRequestSerializer(data=request.query_params)
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
        customer_id = serializer.validated_data["customer_id"]
        try:
            customer = Customer.objects.get(
                organization_id=organization_pk, customer_id=customer_id
            )
        except Customer.DoesNotExist:
            return Response(
                {"status": "error", "detail": "Customer not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        event_name = serializer.validated_data.get("event_name")
        feature_name = serializer.validated_data.get("feature_name")
        subscriptions = Subscription.objects.select_related("billing_plan").filter(
            organization_id=organization_pk,
            status=SUBSCRIPTION_STATUS.ACTIVE,
            customer=customer,
        )
        metrics = []
        features = []
        if event_name:
            subscriptions = subscriptions.prefetch_related(
                "billing_plan__plan_components",
                "billing_plan__plan_components__billable_metric",
                "billing_plan__plan_components__tiers",
            )

            for sub in subscriptions:
                cache_key = f"customer_id:{customer_id}__event_name:{event_name}"
                for component in sub.billing_plan.plan_components.all():
                    metric = component.billable_metric
                    if metric.event_name == event_name:
                        metric_name = metric.billable_metric_name
                        tiers = sorted(
                            component.tiers.all(), key=lambda x: x.range_start
                        )
                        free_limit = (
                            tiers[0].range_end
                            if tiers[0].type == PRICE_TIER_TYPE.FREE
                            else None
                        )
                        total_limit = tiers[-1].range_end
                        subscription_id = sub.subscription_id
                        metric_usage = metric.get_current_usage(sub)
                        if metric_usage is None:
                            continue
                        elif metric_usage == {}:
                            unique_tup_dict = {
                                "event_name": event_name,
                                "metric_name": metric_name,
                                "metric_usage": 0,
                                "metric_free_limit": free_limit,
                                "metric_total_limit": total_limit,
                                "subscription_id": subscription_id,
                                "separate_by_properties": {},
                            }
                            metrics.append(unique_tup_dict)
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
                                "event_name": event_name,
                                "metric_name": metric_name,
                                "metric_usage": usage,
                                "metric_free_limit": free_limit,
                                "metric_total_limit": total_limit,
                                "subscription_id": subscription_id,
                                "separate_by_properties": {},
                            }
                            if len(groupby_vals) > 0:
                                unique_tup_dict["separate_by_properties"] = dict(
                                    zip(component.separate_by, groupby_vals)
                                )
                            metrics.append(unique_tup_dict)
        elif feature_name:
            subscriptions = subscriptions.prefetch_related("billing_plan__features")
            for sub in subscriptions:
                for feature in sub.billing_plan.features.all():
                    if feature.feature_name == feature_name:
                        features.append(
                            {
                                "feature_name": feature_name,
                                "subscription_id": sub.subscription_id,
                            }
                        )
        return Response(
            {"metrics": metrics, "features": features},
            status=status.HTTP_200_OK,
        )


class ImportCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="ImportCustomersRequest",
            fields={
                "source": serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
            },
        ),
        responses={
            200: inline_serializer(
                name="ImportCustomerSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="ImportCustomerFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        source = request.data["source"]
        if source not in [choice[0] for choice in PAYMENT_PROVIDERS.choices]:
            raise AssertionError
        connector = PAYMENT_PROVIDER_MAP[source]
        try:
            num = connector.import_customers(organization)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "detail": f"Error importing customers: {e}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status": "success",
                "detail": f"Customers succesfully imported {num} customers from {source}.",
            },
            status=status.HTTP_201_CREATED,
        )


class ImportPaymentObjectsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="ImportPaymentObjectsRequest",
            fields={
                "source": serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
            },
        ),
        responses={
            200: inline_serializer(
                name="ImportPaymentObjectSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="ImportPaymentObjectFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        source = request.data["source"]
        if source not in [choice[0] for choice in PAYMENT_PROVIDERS.choices]:
            raise AssertionError
        connector = PAYMENT_PROVIDER_MAP[source]
        try:
            num = connector.import_payment_objects(organization)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "detail": f"Error importing payment objects: {e}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        num = sum([len(v) for v in num.values()])
        return Response(
            {
                "status": "success",
                "detail": f"Payment objects succesfully imported {num} payment objects from {source}.",
            },
            status=status.HTTP_201_CREATED,
        )


class TransferSubscriptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="TransferSubscriptionsRequest",
            fields={
                "source": serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices),
                "end_now": serializers.BooleanField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="TransferSubscriptionsSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="TransferSubscriptionsFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        source = request.data["source"]
        if source not in [choice[0] for choice in PAYMENT_PROVIDERS.choices]:
            raise AssertionError
        end_now = request.data.get("end_now", False)
        connector = PAYMENT_PROVIDER_MAP[source]
        try:
            num = connector.transfer_subscriptions(organization, end_now)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "detail": f"Error importing customers: {e}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status": "success",
                "detail": f"Succesfully transferred {num} subscriptions from {source}.",
            },
            status=status.HTTP_201_CREATED,
        )


class ExperimentalToActiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ExperimentalToActiveRequestSerializer(),
        responses={
            200: inline_serializer(
                name="ExperimentalToActiveSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="ExperimentalToActiveFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        serializer = ExperimentalToActiveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        billing_plan = serializer.validated_data["version_id"]
        try:
            billing_plan.status = PLAN_STATUS.ACTIVE
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "detail": f"Error converting experimental plan to active plan: {e}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status": "success",
                "detail": f"Plan {billing_plan} succesfully converted from experimental to active.",
            },
            status=status.HTTP_200_OK,
        )


class PlansByNumCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="PlansByNumCustomersRequest",
            fields={},
        ),
        responses={
            200: inline_serializer(
                name="PlansByNumCustomers",
                fields={
                    "results": serializers.ListField(
                        child=inline_serializer(
                            name="SinglePlanNumCustomers",
                            fields={
                                "plan_name": serializers.CharField(),
                                "num_customers": serializers.IntegerField(),
                                "percent_total": serializers.FloatField(),
                            },
                        )
                    ),
                    "status": serializers.ChoiceField(choices=["success"]),
                },
            ),
        },
    )
    def get(self, request, format=None):
        organization = parse_organization(request)
        plans = (
            Subscription.objects.filter(
                organization=organization, status=SUBSCRIPTION_STATUS.ACTIVE
            )
            .values(plan_name=F("billing_plan__plan__plan_name"))
            .annotate(num_customers=Count("customer"))
            .order_by("-num_customers")
        )
        tot_plans = sum([plan["num_customers"] for plan in plans])
        plans = [
            {**plan, "percent_total": plan["num_customers"] / tot_plans}
            for plan in plans
        ]
        return Response(
            {
                "status": "success",
                "results": plans,
            },
            status=status.HTTP_200_OK,
        )


# class CustomerBalanceAdjustmentView(APIView):
#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         request=inline_serializer(
#             name="CreateBalanceAdjustmentRequest",
#             fields={
#                 "amount": serializers.IntegerField(required=True),
#                 "customer_id": serializers.CharField(required=True),
#                 "amount_currency": serializers.CharField(required=True),
#                 "description": serializers.CharField(),
#             },
#         ),
#         responses={
#             200: inline_serializer(
#                 name="CreateBalanceAdjustmentSuccess",
#                 fields={
#                     "status": serializers.ChoiceField(choices=["success"]),
#                     "detail": serializers.CharField(),
#                 },
#             ),
#             400: inline_serializer(
#                 name="CreateBalanceAdjustmentFailure",
#                 fields={
#                     "status": serializers.ChoiceField(choices=["error"]),
#                     "detail": serializers.CharField(),
#                 },
#             ),
#         },
#     )
#     def get(self, request, format=None):
#         """
#         Get the current settings for the organization.
#         """
#         organization = parse_organization(request)
#         customer_id = request.query_params.get("customer_id")
#         customer_balances_adjustment = CustomerBalanceAdjustment.objects.filter(
#             customer_id=customer_id
#         ).prefetch_related(
#             Prefetch(
#                 "customer",
#                 queryset=Customer.objects.filter(organization=organization),
#                 to_attr="customers",
#             ),
#         )
#         if len(customer_balances_adjustment) == 0:
#             return Response(
#                 {
#                     "error_detail": "CustomerBalanceAdjustmentView with customer_id {} does not exist".format(
#                         customer_id
#                     )
#                 },
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         serializer = CustomerBalanceAdjustmentSerializer(customer_balances_adjustment)
#         return Response(serializer.data, status=status.HTTP_200_OK)


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
        organization = parse_organization(request)
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
