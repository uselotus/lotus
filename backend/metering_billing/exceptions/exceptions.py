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
    default_detail = "Customer ID already exists"
    default_code = "Customer ID already exists"


class DuplicateMetric(APIException):
    status_code = 409
    default_detail = "Metric with that name already exists"
    default_code = "Metric already exists"


class OverlappingSubscription(APIException):
    status_code = 409
    default_detail = "Subscription overlaps with another subscription with the same billing plan and customer"
    default_code = "Subscription overlaps with another subscription with the same billing plan and customer"
