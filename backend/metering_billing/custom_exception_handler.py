import logging

from django.db import DataError
from requests import ConnectionError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # checks if the raised exception is of the type you want to handle
    if isinstance(exc, DataError):
        # defines custom response data
        err_data = {
            "detail": "Database operation failed. Please double check your metrics/events and make sure you're not using a text field where you should be using a numeric field.",
            "callstack": str(exc),
        }

        # logs detail data from the exception being handled
        logging.error(f"[DATA ERROR]: Original error detail and callstack: {exc}")
        # returns a JsonResponse
        return Response(err_data, status=status.HTTP_400_BAD_REQUEST)

    # returns response as handled normally by the framework
    return response
