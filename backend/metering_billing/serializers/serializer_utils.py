import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class SlugRelatedFieldWithOrganization(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = self.queryset
        org = self.context.get("organization", None)
        queryset = queryset.filter(organization=org)
        return queryset


class SlugRelatedFieldWithOrganizationPK(serializers.SlugRelatedField):
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
        if not isinstance(data, str):
            raise ValidationError(
                "Input must be a string beginning with the prefix {} and followed by he compact hex representation of the UUID, not including hyphens.".format(
                    self.prefix
                )
            )
        if not data.startswith(self.prefix):
            raise ValidationError(
                "Input must be a string beginning with the prefix {} and followed by he compact hex representation of the UUID, not including hyphens.".format(
                    self.prefix
                )
            )
        data = data[len(self.prefix) :]
        data = uuid.UUID(data)
        data = super().to_internal_value(data)
        return data

    def to_representation(self, value) -> str:
        return self.prefix + value.hex


@extend_schema_field(serializers.RegexField(regex=r"org_[0-9a-f]{32}"))
class OrganizationUUIDField(UUIDPrefixField):
    def __init__(self, *args, **kwargs):
        super().__init__("org_", *args, **kwargs)
