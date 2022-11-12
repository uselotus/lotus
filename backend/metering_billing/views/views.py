from decimal import Decimal

import posthog
from dateutil import parser
from django.conf import settings
from django.db.models import Count, F, Prefetch, Q, Sum
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth import parse_organization
from metering_billing.invoice import generate_invoice
from metering_billing.models import APIToken, BillableMetric, Customer, Subscription
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.auth_serializers import *
from metering_billing.serializers.backtest_serializers import *
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from metering_billing.serializers.request_serializers import *
from metering_billing.serializers.response_serializers import *
from metering_billing.utils import (
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
from rest_framework import status
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
        all_org_billable_metrics = BillableMetric.objects.filter(
            organization=organization
        )

        return_dict = {
            "daily_usage_revenue_period_1": {},
            "total_revenue_period_1": Decimal(0),
            "daily_usage_revenue_period_2": {},
            "total_revenue_period_2": Decimal(0),
        }
        if all_org_billable_metrics.count() > 0:
            for billable_metric in all_org_billable_metrics:
                for p_start, p_end, p_num in [
                    (p1_start, p1_end, 1),
                    (p2_start, p2_end, 2),
                ]:
                    return_dict[f"daily_usage_revenue_period_{p_num}"][
                        billable_metric.id
                    ] = {
                        "metric": str(billable_metric),
                        "data": {
                            x: Decimal(0)
                            for x in periods_bwn_twodates(
                                USAGE_CALC_GRANULARITY.DAILY, p_start, p_end
                            )
                        },
                        "total_revenue": Decimal(0),
                    }
            for p_start, p_end, p_num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
                total_period_rev = Decimal(0)
                subs = (
                    Subscription.objects.filter(
                        Q(start_date__range=[p_start, p_end])
                        | Q(end_date__range=[p_start, p_end]),
                        organization=organization,
                    )
                    .select_related("billing_plan")
                    .select_related("customer")
                    .prefetch_related("billing_plan__components")
                    .prefetch_related("billing_plan__components__billable_metric")
                )
                for sub in subs:
                    bp = sub.billing_plan
                    flat_bill_date = (
                        sub.start_date
                        if bp.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE
                        else sub.end_date
                    )
                    if p_start <= flat_bill_date <= p_end:
                        total_period_rev += bp.flat_rate.amount
                    for plan_component in bp.components.all():
                        billable_metric = plan_component.billable_metric
                        revenue_per_day = plan_component.calculate_total_revenue(sub)
                        metric_dict = return_dict[
                            f"daily_usage_revenue_period_{p_num}"
                        ][billable_metric.id]
                        for date, d in revenue_per_day.items():
                            if date in metric_dict["data"]:
                                usage_cost = Decimal(d["revenue"])
                                metric_dict["data"][date] += usage_cost
                                metric_dict["total_revenue"] += usage_cost
                                total_period_rev += usage_cost
                return_dict[f"total_revenue_period_{p_num}"] = total_period_rev
        for p_num in [1, 2]:
            dailies = return_dict[f"daily_usage_revenue_period_{p_num}"]
            dailies = [daily_dict for metric_id, daily_dict in dailies.items()]
            return_dict[f"daily_usage_revenue_period_{p_num}"] = dailies
            for dic in dailies:
                dic["data"] = [
                    {"date": str(k.date()), "metric_revenue": v}
                    for k, v in dic["data"].items()
                ]
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
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
        if type(q_start) == str:
            q_start = parser.parse(q_start).date()
        if type(q_end) == str:
            q_end = parser.parse(q_end).date()
        q_start = date_as_min_dt(q_start)
        q_end = date_as_max_dt(q_end)

        metrics = BillableMetric.objects.filter(organization=organization)
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
            for customer_name, period_dict in usage_summary.items():
                for datetime, qty in period_dict.items():
                    qty = convert_to_decimal(qty)
                    if datetime not in metric_dict["data"]:
                        metric_dict["data"][datetime] = {
                            "total_usage": Decimal(0),
                            "customer_usages": {},
                        }
                    date_dict = metric_dict["data"][datetime]
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
                metric_dict["top_n_customers"] = list(x[0] for x in top_n_customers)
                metric_dict["top_n_customers_usage"] = list(
                    x[1] for x in top_n_customers
                )
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
        APIToken.objects.filter(organization=organization).delete()
        api_key, key = APIToken.objects.create_key(
            name="new_api_key", organization=organization
        )
        try:
            user = self.request.user
        except:
            user = None
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else (user.username if user else organization.company_name + " (Unknown)"),
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


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            inline_serializer(
                name="CustomerDetailRequestSerializer",
                fields={"customer_id": serializers.CharField()},
            ),
        ],
        responses={
            200: CustomerDetailSerializer,
            400: inline_serializer(
                name="CustomerDetailErrorResponseSerializer",
                fields={"error_detail": serializers.CharField()},
            ),
        },
    )
    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        customer_id = request.query_params.get("customer_id")
        try:
            customer = (
                Customer.objects.filter(
                    organization=organization, customer_id=customer_id
                )
                .prefetch_related(
                    Prefetch(
                        "customer_subscriptions",
                        queryset=Subscription.objects.filter(organization=organization),
                        to_attr="subscriptions",
                    ),
                    Prefetch(
                        "subscriptions__billing_plan",
                        queryset=PlanVersion.objects.filter(organization=organization),
                        to_attr="billing_plans",
                    ),
                )
                .get()
            )
        except Customer.DoesNotExist:
            return Response(
                {
                    "error_detail": "Customer with customer_id {} does not exist".format(
                        customer_id
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_amount_due = customer.get_outstanding_revenue()
        invoices = Invoice.objects.filter(
            organization=organization,
            customer=customer,
        )
        serializer = CustomerDetailSerializer(
            customer,
            context={
                "total_amount_due": total_amount_due,
                "invoices": invoices,
            },
        )
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
            serializer = CustomerWithRevenueSerializer(
                customer,
                context={
                    "total_amount_due": total_amount_due,
                },
            )
            cust.append(serializer.data)
        cust = make_all_decimals_floats(cust)
        return Response(cust, status=status.HTTP_200_OK)


class DraftInvoiceView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[DraftInvoiceRequestSerializer],
        responses={200: DraftInvoiceSerializer},
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
        subs = Subscription.objects.filter(
            customer=customer,
            organization=organization,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )
        invoices = [generate_invoice(sub, draft=True) for sub in subs]
        serializer = DraftInvoiceSerializer(invoices, many=True)
        try:
            user = self.request.user
        except:
            user = None
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else (user.username if user else organization.company_name + " (Unknown)"),
            event="draft_invoice",
            properties={"organization": organization.company_name},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class GetCustomerAccessView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[GetCustomerAccessRequestSerializer],
        responses={
            200: inline_serializer(
                name="GetCustomerAccessSuccess",
                fields={
                    "access": serializers.BooleanField(),
                    "usages": serializers.ListField(
                        child=inline_serializer(
                            name="MetricUsageSerializer",
                            fields={
                                "metric_name": serializers.CharField(),
                                "metric_usage": serializers.FloatField(),
                                "metric_limit": serializers.FloatField(),
                                "access": serializers.BooleanField(),
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
        serializer = GetCustomerAccessRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(request)
        try:
            user = self.request.user
        except:
            user = None
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else (user.username if user else organization.company_name + " (Unknown)"),
            event="get_access",
            properties={"organization": organization.company_name},
        )
        customer_id = serializer.validated_data["customer_id"]
        try:
            customer = Customer.objects.get(
                organization=organization, customer_id=customer_id
            )
        except Customer.DoesNotExist:
            return Response(
                {"status": "error", "detail": "Customer not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        event_name = serializer.validated_data.get("event_name")
        feature_name = serializer.validated_data.get("feature_name")
        event_limit_type = serializer.validated_data.get("event_limit_type")
        subscriptions = Subscription.objects.select_related("billing_plan").filter(
            organization=organization,
            status=SUBSCRIPTION_STATUS.ACTIVE,
            customer=customer,
        )
        if event_name:
            subscriptions = subscriptions.prefetch_related(
                "billing_plan__components", "billing_plan__components__billable_metric"
            )
            metric_usages = {}
            for sub in subscriptions:
                for component in sub.billing_plan.components.all():
                    if component.billable_metric.event_name == event_name:
                        metric = component.billable_metric
                        if event_limit_type == "free":
                            metric_limit = component.free_metric_units
                        elif event_limit_type == "total":
                            metric_limit = component.max_metric_units
                        if not metric_limit:
                            metric_usages[metric.billable_metric_name] = {
                                "metric_usage": None,
                                "metric_limit": None,
                                "access": True,
                            }
                            continue
                        metric_usage = metric.get_current_usage(sub)
                        metric_usages[metric.billable_metric_name] = {
                            "metric_usage": metric_usage,
                            "metric_limit": metric_limit,
                            "access": metric_usage < metric_limit,
                        }
            if all(v["access"] for k, v in metric_usages.items()):
                return Response(
                    {
                        "access": True,
                        "usages": [
                            v.update({"metric_name": k})
                            for k, v in metric_usages.items()
                        ],
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "access": False,
                        "usages": [
                            v.update({"metric_name": k})
                            for k, v in metric_usages.items()
                        ],
                    },
                    status=status.HTTP_200_OK,
                )
        elif feature_name:
            subscriptions = subscriptions.prefetch_related("billing_plan__features")
            for sub in subscriptions:
                for feature in sub.billing_plan.features.all():
                    if feature.feature_name == feature_name:
                        return Response(
                            {"access": True},
                            status=status.HTTP_200_OK,
                        )

        return Response(
            {"access": False},
            status=status.HTTP_200_OK,
        )


class BatchCreateCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="BatchCreateCustomersRequest",
            fields={
                "customers": CustomerSerializer(many=True),
                "duplicate_email_behavior": serializers.ChoiceField(
                    choices=["ignore", "error", "update"]
                ),
            },
        ),
        responses={
            201: inline_serializer(
                name="BatchCreateCustomerSuccess",
                fields={
                    "success": serializers.ChoiceField(choices=["all", "some"]),
                    "failed_customer_emails": serializers.ListField(required=False),
                },
            ),
            400: inline_serializer(
                name="BatchCreateCustomerFailure",
                fields={
                    "success": serializers.ChoiceField(choices=["none"]),
                    "failed_customer_emails": serializers.ListField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        customers = CustomerSerializer(data=request.data.get("customers"), many=True)
        customers.is_valid(raise_exception=True)
        behavior = request.data.get("duplicate_email_behavior", "ignore")

        failed_customer_emails = []
        for customer in customers.validated_data:
            c_obj = Customer.objects.filter(
                organization=organization, email=customer["email"]
            )
            if c_obj.exists():
                c_obj = c_obj.first()
                if behavior == "ignore":
                    continue
                elif behavior == "error":
                    failed_customer_emails.append(customer["email"])
                elif behavior == "update":
                    pp_id = customer.pop("payment_provider_id", None)
                    pp = customer.pop("payment_provider", None)
                    c_obj.update(**customer)
                    if pp:
                        c_obj.update(payment_provider=pp)
                        if pp_id:
                            integrations = c_obj.first().integrations
                            if pp in integrations:
                                integrations[pp]["payment_provider_id"] = pp_id
                            else:
                                integrations[pp] = {"id": pp_id}
                            c_obj.update(integrations=integrations)
            else:
                CustomerSerializer(data=customer).save()
                Customer.objects.create(organization=organization, **customer)

        if len(failed_customer_emails) == len(customers.validated_data):
            return Response(
                {
                    "success": "none",
                    "failed_customer_emails": failed_customer_emails,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status": "success" if len(failed_customer_emails) == 0 else "some",
                "failed_customer_emails": failed_customer_emails,
            },
            status=status.HTTP_201_CREATED,
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
        assert source in [choice[0] for choice in PAYMENT_PROVIDERS.choices]
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
        assert source in [choice[0] for choice in PAYMENT_PROVIDERS.choices]
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
        assert source in [choice[0] for choice in PAYMENT_PROVIDERS.choices]
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
