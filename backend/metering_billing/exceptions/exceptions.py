from rest_framework.exceptions import APIException


class OrganizationMismatch(APIException):
    status_code = 401
    default_detail = (
        "Provided both API key and session authentication but organization didn't match"
    )
    default_code = "authentication_failure"


class SubscriptionAlreadyEnded(APIException):
    status_code = 400
    default_detail = "Subscription already ended"
    default_code = "invalid_state"


class InvalidOperation(APIException):
    status_code = 400
    default_detail = "Invalid operation"
    default_code = "invalid_operation"


class UserNoOrganization(APIException):
    status_code = 401
    default_detail = "User does not have an organization"
    default_code = "authentication_failure"


class RepeatedOperation(APIException):
    status_code = 401
    default_detail = "repeated_operation"
    default_code = "repeated_operation"


class NoMatchingAPIKey(APIException):
    status_code = 401
    default_detail = "API Key not known"
    default_code = "api_key_not_known"


class NoAPIKeyProvided(APIException):
    status_code = 401
    default_detail = "No API key provided"
    default_code = "no_api_key_provided"


class DuplicateWebhookEndpoint(APIException):
    status_code = 400
    default_detail = "Webhook endpoint already exists"
    default_code = "duplicate_resource"


class DuplicateCustomer(APIException):
    status_code = 400
    default_detail = "Customer with that customer_id already exists"
    default_code = "duplicate_resource"


class DuplicateMetric(APIException):
    status_code = 400
    default_detail = "Metric with that name already exists"
    default_code = "duplicate_resource"


class DuplicateUser(APIException):
    status_code = 400
    default_detail = "User with that email already exists"
    default_code = "duplicate_resource"


class DuplicateOrganization(APIException):
    status_code = 400
    default_detail = "Organization with that name already exists"
    default_code = "duplicate_resource"


class RepeatedEventIdempotency(APIException):
    status_code = 400
    default_detail = "Idempotency key already exists"
    default_code = "Idempotency key already exists"


class SwitchPlanDurationMismatch(APIException):
    status_code = 400
    default_detail = "Switch plan duration does not match current plan duration"
    default_code = "invalid_state"


class SwitchPlanSamePlanException(APIException):
    status_code = 400
    default_detail = "Switch plan is the same as current plan"
    default_code = "invalid_state"


class NotFoundException(APIException):
    status_code = 404
    default_detail = "Resource was not found"
    default_code = "resource_not_found"


class DatabaseOperationFailed(APIException):
    status_code = 500
    default_detail = "Database operation failed. Please double-check your metrics/events and make sure you're not using a text field where you should be using a numeric field."
    default_code = "aggregation_engine_failure"


class AggregationEngineFailure(APIException):
    status_code = 500
    default_detail = "Aggregation engine failed to perform aggregation"
    default_code = "aggregation_engine_failure"


class MetricValidationFailed(APIException):
    status_code = 400
    default_detail = "Metric validation failed"
    default_code = "Metric validation failed"


class ExternalConnectionInvalid(APIException):
    status_code = 400
    default_detail = "External connection invalid"
    default_code = "external_connection_invalid"


class ExternalConnectionFailure(APIException):
    status_code = 500
    default_detail = "External connection failed"
    default_code = "external_connection_failed"


class NotEditable(APIException):
    status_code = 400
    default_detail = "This resource is not editable"
    default_code = "invalid_request"


class RegistrationFailure(APIException):
    status_code = 400
    default_detail = "Registration failed"
    default_code = "registration_failure"


class ServerError(APIException):
    status_code = 500
    default_detail = "Internal server error"
    default_code = "server_error"


class PrepaymentMissingUnits(APIException):
    status_code = 400
    default_detail = "Input error"
    default_code = "prepayment_cant_determine_units"


class InvalidRequest(APIException):
    status_code = 400
    default_detail = "Invalid request"
    default_code = "invalid_request"


class MethodNotAllowed(APIException):
    status_code = 405
    default_detail = "Method not allowed"
    default_code = "method_not_allowed"


class StripeWebhookFailure(APIException):
    status_code = 400
    default_detail = "Stripe webhook invalid"
    default_code = "stripe_webhook_invalid"


class OverlappingPlans(APIException):
    status_code = 400
    default_detail = "Overlapping plans"
    default_code = "overlapping_plans"


class AlignmentEngineFailure(APIException):
    status_code = 500
    default_detail = "Alignment engine failed to perform alignment"
    default_code = "alignment_engine_failure"


class IntermediateBillingEngineFailure(APIException):
    status_code = 500
    default_detail = "Intermediate billing engine ran into an unexpected state"
    default_code = "intermediate_billing_engine_failure"
