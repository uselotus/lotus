from rest_framework.exceptions import APIException


class OrganizationMismatch(APIException):
    status_code = 406
    default_detail = (
        "Provided both API key and session authentication but organization didn't match"
    )
    default_code = "Mismatched API key and session authentication"


class UserNoOrganization(APIException):
    status_code = 403
    default_detail = "User does not have an organization"
    default_code = "User has no organization"
