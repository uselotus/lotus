import datetime
import uuid

import pytz
from dateutil.parser import parse
from django.core.serializers.json import DjangoJSONEncoder
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from timezone_field.rest_framework import TimeZoneSerializerField


@extend_schema_field(serializers.ChoiceField(choices=pytz.common_timezones))
class TimeZoneSerializerField(TimeZoneSerializerField):
    pass


class ConvertEmptyStringToNullMixin:
    def recursive_convert_empty_string_to_none(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                self.recursive_convert_empty_string_to_none(value)
            elif value == "":
                data[key] = None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        self.recursive_convert_empty_string_to_none(data)
        return data


class TimezoneFieldMixin:
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        customer = getattr(instance, "customer", None)
        timezone_field = "timezone"
        if customer is not None:
            timezone = getattr(customer, timezone_field, None)
        else:
            organization = getattr(instance, "organization", None)
            timezone = (
                getattr(organization, timezone_field, None)
                if organization is not None
                else None
            )
        if timezone is not None:
            for field_name, value in representation.items():
                if value is None:
                    representation[field_name] = None
                field = self.fields.get(field_name)
                if isinstance(field, serializers.DateTimeField) and value is not None:
                    if isinstance(value, str):
                        value = parse(value)
                    representation[field_name] = value.astimezone(timezone).isoformat()
        return representation


class DjangoJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            r = obj.isoformat()
            if r.endswith("+00:00"):
                r = r[:-6] + "Z"
            return r
        return super(DjangoJSONEncoder, self).default(obj)


class SlugRelatedFieldWithOrganization(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = self.queryset
        org = self.context.get("organization", None)
        queryset = queryset.filter(organization=org)
        return queryset

    def to_internal_value(self, data):
        from lotus.backend.metering_billing.models import (
            CustomerBalanceAdjustment,
            Feature,
            Invoice,
            Metric,
            Organization,
            Plan,
            PlanVersion,
        )

        if self.queryset.model is CustomerBalanceAdjustment:
            data = BalanceAdjustmentUUIDField().to_internal_value(data)
        elif self.queryset.model is Metric:
            data = MetricUUIDField().to_internal_value(data)
        elif self.queryset.model is Plan:
            try:
                data = PlanUUIDField().to_internal_value(data)
            except ValidationError:
                data = AddonUUIDField().to_internal_value(data)
        elif self.queryset.model is PlanVersion:
            data = PlanVersionUUIDField().to_internal_value(data)
        elif self.queryset.model is Feature:
            data = FeatureUUIDField().to_internal_value(data)
        elif self.queryset.model is Organization:
            data = OrganizationUUIDField().to_internal_value(data)
        elif self.queryset.model is Invoice:
            data = InvoiceUUIDField().to_internal_value(data)
        return super().to_internal_value(data)

    def to_representation(self, obj):
        from lotus.backend.metering_billing.models import (
            CustomerBalanceAdjustment,
            Feature,
            Invoice,
            Metric,
            Organization,
            Plan,
            PlanVersion,
        )

        repr = super().to_representation(obj)
        if isinstance(obj, CustomerBalanceAdjustment):
            return BalanceAdjustmentUUIDField().to_representation(obj.adjustment_id)
        elif isinstance(obj, Metric):
            return MetricUUIDField().to_representation(obj.metric_id)
        elif isinstance(obj, Plan) and obj.addon_spec is None:
            return PlanUUIDField().to_representation(obj.plan_id)
        elif isinstance(obj, Plan) and obj.addon_spec is not None:
            return AddonUUIDField().to_representation(obj.plan_id)
        elif isinstance(obj, PlanVersion):
            return PlanVersionUUIDField().to_representation(obj.version_id)
        elif isinstance(obj, Feature):
            return FeatureUUIDField().to_representation(obj.feature_id)
        elif isinstance(obj, Organization):
            return OrganizationUUIDField().to_representation(obj.organization_id)
        elif isinstance(obj, Invoice):
            return InvoiceUUIDField().to_representation(obj.invoice_id)
        return repr


class SlugRelatedFieldWithOrganizationPK(SlugRelatedFieldWithOrganization):
    def get_queryset(self):
        queryset = self.queryset
        org = self.context.get("organization_pk", None)
        queryset = queryset.filter(organization_id=org)
        return queryset


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    class Meta:
        fields = ("email",)


class UUIDPrefixField(serializers.UUIDField):
    def __init__(self, prefix: str, *args, **kwargs):
        self.prefix = prefix
        super().__init__(*args, **kwargs)
        self.uuid_format = "hex"

    def to_internal_value(self, data) -> uuid.UUID:
        if not isinstance(data, (str, uuid.UUID)):
            raise ValidationError(
                "Input must be a string beginning with the prefix {} and followed by the compact hex representation of the UUID, not including hyphens.".format(
                    self.prefix
                )
            )
        if isinstance(data, str):
            data = data.replace("-", "")
            data = data.replace(f"{self.prefix}", "")
            try:
                data = uuid.UUID(data)
            except ValueError:
                raise ValidationError(
                    "Input must be a string beginning with the prefix {} and followed by the compact hex representation of the UUID, not including hyphens.".format(
                        self.prefix
                    )
                )
        data = super().to_internal_value(data)
        return data

    def to_representation(self, value) -> str:
        return self.prefix + value.hex


@extend_schema_field(serializers.RegexField(regex=r"org_[0-9a-f]{32}"))
class OrganizationUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("org_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"btest_[0-9a-f]{32}"))
class BacktestUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("btest_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"baladj_[0-9a-f]{32}"))
class BalanceAdjustmentUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("baladj_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"metric_[0-9a-f]{32}"))
class MetricUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("metric_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"orgset_[0-9a-f]{32}"))
class OrganizationSettingUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("orgset_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"plan_[0-9a-f]{32}"))
class PlanUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("plan_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"invoice_[0-9a-f]{32}"))
class InvoiceUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("invoice_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"plan_version_[0-9a-f]{32}"))
class PlanVersionUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("plan_version_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"feature_[0-9a-f]{32}"))
class FeatureUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("feature_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"sub_[0-9a-f]{32}"))
class SubscriptionUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("sub_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"sr_[0-9a-f]{32}"))
class SubscriptionRecordUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("sr_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"usg_alert_[0-9a-f]{32}"))
class UsageAlertUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("usg_alert_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"whend_[0-9a-f]{32}"))
class WebhookEndpointUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("whend_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"whsec_[0-9a-f]{32}"))
class WebhookSecretUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("whsec_", *args, **kwargs)


@extend_schema_field(serializers.RegexField(regex=r"addon_[0-9a-f]{32}"))
class AddonUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("addon_", *args, **kwargs)
