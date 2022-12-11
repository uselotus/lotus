from rest_framework.exceptions import APIException


class OrganizationMismatch(APIException):
    status_code = 406
    default_detail = (
        "Provided both API key and session authentication but organization didn't match"
    )
    default_code = "Mismatched API key and session authentication"


class NoMatchingAPIKey(APIException):
    status_code = 403
    default_detail = "API Key not known"
    default_code = "API Key not known"


class DuplicateWebhookEndpoint(APIException):
    status_code = 409
    default_detail = "Webhook endpoint already exists"
    default_code = "Webhook endpoint already exists"


class RepeatedEventIdempotency(APIException):
    status_code = 409
    default_detail = "Idempotency key already exists"
    default_code = "Idempotency key already exists"


class UserNoOrganization(APIException):
    status_code = 403
    default_detail = "User does not have an organization"
    default_code = "User has no organization"


class DuplicateCustomerID(APIException):
    status_code = 409
    default_detail = "Customer with that customer_id already exists"
    default_code = "Customer ID already exists"


class DuplicateMetric(APIException):
    status_code = 409
    default_detail = "Metric with that name already exists"
    default_code = "Metric already exists"


class SwitchPlanDurationMismatch(APIException):
    status_code = 409
    default_detail = "Switch plan duration does not match current plan duration"
    default_code = "Switch plan duration mismatch"


class SwitchPlanSamePlanException(APIException):
    status_code = 409
    default_detail = "Switch plan is the same as current plan"
    default_code = "Switch plan same as current plan"


class SubscriptionNotFoundException(APIException):
    status_code = 404
    default_detail = "Subscription with given customer_id and plan_id not found"
    default_code = "Subscription not found"
