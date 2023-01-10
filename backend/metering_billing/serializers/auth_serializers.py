from rest_framework import serializers


class RegistrationDetailSerializer(serializers.Serializer):
    organization_name_name = serializers.CharField(allow_blank=True)
    industry = serializers.CharField(allow_blank=True)
    email = serializers.CharField()
    password = serializers.CharField()
    username = serializers.CharField()

    def validate(self, attrs):
        token = self.context.get("token", None)
        if not token and attrs.get("organization_name") is None:
            raise serializers.ValidationError(
                "Company name is required for registration"
            )
        return super().validate(attrs)


class RegistrationSerializer(serializers.Serializer):
    register = RegistrationDetailSerializer()


class DemoRegistrationDetailSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField()
    username = serializers.CharField()


class DemoRegistrationSerializer(serializers.Serializer):
    register = DemoRegistrationDetailSerializer()
