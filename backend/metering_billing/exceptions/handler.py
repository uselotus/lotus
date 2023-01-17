from django.db import DataError
from drf_standardized_errors.formatter import ExceptionFormatter
from drf_standardized_errors.handler import ExceptionHandler
from drf_standardized_errors.types import ErrorResponse, ErrorType
from metering_billing.exceptions.exceptions import DatabaseOperationFailed


class CustomHandler(ExceptionHandler):
    def convert_known_exceptions(self, exc: Exception) -> Exception:
        if isinstance(exc, DataError):
            return DatabaseOperationFailed()
        else:
            return super().convert_known_exceptions(exc)


class RFC7807Formatter(ExceptionFormatter):
    def format_error_response(self, error_response: ErrorResponse):
        error = error_response.errors[0]
        if error_response.type == ErrorType.VALIDATION_ERROR:
            url_error_type = "validation-error"
        elif error_response.type == ErrorType.CLIENT_ERROR:
            url_error_type = "client-error"
        elif error_response.type == ErrorType.SERVER_ERROR:
            url_error_type = "server-error"
        return_d = {
            "type": f"https://docs.uselotus.io/errors/error-responses#{url_error_type}",
            "detail": error.detail,
            "title": error.code,
        }
        if (
            len(error_response.errors) > 1
            or error_response.type == ErrorType.VALIDATION_ERROR
        ):
            return_d["validation_errors"] = [
                {"code": x.code, "detail": x.detail, "attr": x.attr}
                for x in error_response.errors
            ]
        return return_d
