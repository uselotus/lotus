import csv
import datetime
import io
import logging

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from metering_billing.invoice_pdf import s3_bucket_exists, s3_file_exists
from metering_billing.models import Invoice, Organization
from metering_billing.utils import convert_to_datetime, now_utc

logger = logging.getLogger("django.server")

try:
    s3 = boto3.resource(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
except ClientError:
    pass

BUCKET_NAME = "lotus-invoice-csvs-d8d79027"
CSV_FOLDER = "invoice_csvs"


def get_key(organization, csv_folder, csv_filename):
    organization_id = organization.organization_id.hex
    team = organization.team
    team_id = team.team_id.hex

    key = f"{team_id}/{organization_id}/{csv_folder}/{csv_filename}.csv"
    return key


def generate_invoices_csv(organization, start_date=None, end_date=None):
    # Format start and end dates as YYMMDD
    csv_filename = get_csv_filename(organization, start_date, end_date)

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    invoices = organization.invoices.filter().select_related("customer")
    if start_date:
        start_time = convert_to_datetime(
            start_date, date_behavior="min", tz=organization.timezone
        )
        invoices = invoices.filter(issue_date__gte=start_time)
    if end_date:
        end_time = convert_to_datetime(
            end_date, date_behavior="max", tz=organization.timezone
        )
        invoices = invoices.filter(issue_date__lte=end_time)
    writer.writerow(
        [
            "External ID",
            "Customer",
            "Date",
            "Date Created",
            "Due Date",
            "End Date",
            "Posting Period",
            "Amount Paid",
            "Amount Remaining",
        ]
    )

    for invoice in invoices:
        tot = invoice.cost_due
        amount_paid = tot if invoice.payment_status == Invoice.PaymentStatus.PAID else 0
        amount_remaining = tot - amount_paid
        due_date = invoice.due_date or invoice.issue_date
        writer.writerow(
            [
                invoice.invoice_number,
                invoice.customer.customer_id,
                invoice.issue_date.strftime("%m/%d/%Y"),
                invoice.issue_date.strftime("%m/%d/%Y"),
                due_date.strftime("%m/%d/%Y"),
                invoice.issue_date.strftime("%m/%d/%Y"),
                invoice.issue_date.strftime("%B %Y"),
                amount_paid,
                amount_remaining,
            ]
        )
    upload_csv(organization, csv_buffer, CSV_FOLDER, csv_filename)


def upload_csv(organization, csv_buffer, csv_folder, csv_filename):
    # If the organization is not an external demo organization
    if (
        not settings.DEBUG
        and organization.organization_type
        != Organization.OrganizationType.EXTERNAL_DEMO
    ):
        try:
            # Upload the file to s3

            if settings.DEBUG:
                bucket_name = "dev-" + BUCKET_NAME
            else:
                bucket_name = BUCKET_NAME

            if s3_bucket_exists(bucket_name):
                logger.error("Bucket exists")
            else:
                s3.create_bucket(Bucket=bucket_name, ACL="private")
                logger.error("Created bucket", bucket_name)

            key = get_key(organization, csv_folder, csv_filename)
            csv_bytes = csv_buffer.getvalue().encode()
            print("uploading", key)
            s3.Bucket(bucket_name).upload_fileobj(io.BytesIO(csv_bytes), key)
            print("uploaded", key)

        except Exception as e:
            print(e)


def get_csv_presigned_url(organization, start_date=None, end_date=None):
    # Format start and end dates as YYMMDD
    csv_filename = get_csv_filename(organization, start_date, end_date)

    # if settings.DEBUG:
    if (
        settings.DEBUG
        or organization.organization_type == Organization.OrganizationType.EXTERNAL_DEMO
    ):
        bucket_name = "dev-" + BUCKET_NAME
        return {"exists": False, "url": ""}

    else:
        bucket_name = "dev-" + BUCKET_NAME
        key = get_key(organization, CSV_FOLDER, csv_filename)
        exists = s3_file_exists(bucket_name=bucket_name, key=key)
        if not exists:
            generate_invoices_csv(organization, start_date, end_date)
        s3_resource = boto3.resource("s3")
        bucket = s3_resource.Bucket(bucket_name)
        object = bucket.Object(key)
        url = object.meta.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=3600,
        )
    return {"exists": True, "url": url}


def get_csv_filename(organization, start_date, end_date):
    if start_date is not None and end_date is not None:
        start_date_str = datetime.datetime.strftime(start_date, "%y%m%d")
        end_date_str = datetime.datetime.strftime(end_date, "%y%m%d")
        csv_filename = f"{start_date_str}-{end_date_str}"
    elif start_date is not None:
        now = now_utc().astimezone(organization.timezone)
        start_date_str = datetime.datetime.strftime(start_date, "%y%m%d")
        now_str = datetime.datetime.strftime(now, "%y%m%d")
        csv_filename = f"{start_date_str}-{now_str}"
    elif end_date is not None:
        end_date_str = (
            datetime.datetime.strftime(end_date, "%y%m%d") if end_date else ""
        )
        csv_filename = f"start-{end_date_str}"
    else:
        now = now_utc().astimezone(organization.timezone)
        now_str = datetime.datetime.strftime(now, "%y%m%d")
        csv_filename = f"start-{now_str}"
    return csv_filename


# def generate_subscription_plan_csv(organization):
#     # create a file-like object for the CSV data
#     buffer = io.StringIO()
#     writer = csv.writer(buffer)

#     writer.writerow(
#         [
#             "Subscription Plan Name",
#             "Initial Term",
#             "Location",
#             "Income Account",
#             "Subscription Plan Members: Line Number",
#             "Subscription Plan Members: Item",
#             "Subscription Plan Members: Type",
#         ]
#     )
#     for plan in organization.plans.filter(status=PLAN_STATUS.ACTIVE):
#         for pv in plan.plan_versions.filter(status=PLAN_STATUS.ACTIVE):
#             subscription_plan_name = str(pv)
#             initial_term = (
#                 "12 Month"
#                 if plan.duration == PLAN_DURATION.YEARLY
#                 else "1 Month"
#                 if plan.duration == PLAN_DURATION.MONTHLY
#                 else "3 Month"
#             )
#             i = 1
#             for charge in pv.recurring_charges.all():
#                 row = ["", "", "", "", i, charge.name, "Recurring"]
#                 if i == 1:
#                     row[0] = subscription_plan_name
#                     row[1] = initial_term
#                 writer.writerow(row)
#                 i += 1
#             for component in pv.plan_components.all():
#                 row = ["", "", "", "", i, str(component), "Usage"]
#                 if i == 1:
#                     row[0] = subscription_plan_name
#                     row[1] = initial_term
#                 writer.writerow(row)
#                 i += 1
#     return buffer
