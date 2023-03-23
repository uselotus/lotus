import csv
import datetime
import io
import logging

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils.text import slugify

from metering_billing.invoice_pdf import s3_bucket_exists, s3_file_exists
from metering_billing.models import Organization
from metering_billing.s3_utils import get_bucket_name
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

CSV_FOLDER = "invoice_csvs"


def get_key(organization, csv_folder, csv_filename):
    organization_id = organization.organization_id.hex
    key = f"{organization_id}/{csv_folder}/{csv_filename}.csv"
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
            # HEADER
            "externalId",
            "entity",  # customer
            "terms",  # unsure about this one, can work on case-by case
            "tranDate",  # issue date
            "postingPeriod",  # mmm yyyy format of issue date
            "dueDate",  # due date
            "currency",  # 3 letter iso code
            # LINE ITEMS
            "item",  # lets make this the internal lotus IDs of the plans
            "description",
            "quantity",
            "rate",
            "amount",
            "taxCode",
        ]
    )

    for invoice in invoices:
        externalId = invoice.invoice_number
        entity = invoice.customer.customer_id
        terms = None
        tranDate = invoice.issue_date.strftime("%m/%d/%Y")
        postingPeriod = invoice.issue_date.strftime("%B %Y")
        dueDate = invoice.due_date.strftime("%m/%d/%Y") if invoice.due_date else None
        currency = invoice.currency.code
        for line_item in invoice.line_items.all():
            if line_item.associated_recurring_charge:
                item = (
                    "recurring_charge_"
                    + line_item.associated_recurring_charge.recurring_charge_id.hex
                )
            elif line_item.associated_plan_component:
                item = (
                    "usage_component_"
                    + line_item.associated_plan_component.usage_component_id.hex
                )
            else:
                item = line_item.name
            description = line_item.name
            quantity = line_item.quantity or 1
            amount = line_item.amount
            rate = amount / quantity
            taxCode = None
            writer.writerow(
                [
                    externalId,
                    entity,
                    terms,
                    tranDate,
                    postingPeriod,
                    dueDate,
                    currency,
                    item,
                    description,
                    quantity,
                    rate,
                    amount,
                    taxCode,
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
            bucket_name, prod = get_bucket_name(organization)
            if s3_bucket_exists(bucket_name):
                logger.error("Bucket exists")
            else:
                s3.create_bucket(Bucket=bucket_name, ACL="private")
                logger.error("Created bucket", bucket_name)

            key = get_key(organization, csv_folder, csv_filename)
            if not prod:
                team_id = organization.team.team_id.hex
                team = organization.team
                team_id = team.team_id.hex + "-" + slugify(team.name)
                key = f"{team_id}/{key}"
            csv_bytes = csv_buffer.getvalue().encode()
            s3.Bucket(bucket_name).upload_fileobj(io.BytesIO(csv_bytes), key)

        except Exception as e:
            print(e)


def get_invoices_csv_presigned_url(organization, start_date=None, end_date=None):
    # Format start and end dates as YYMMDD
    csv_filename = get_csv_filename(organization, start_date, end_date)
    bucket_name, prod = get_bucket_name(organization)
    key = get_key(organization, CSV_FOLDER, csv_filename)
    if not prod:
        team_id = organization.team.team_id.hex
        team = organization.team
        team_id = team.team_id.hex + "-" + slugify(team.name)
        key = f"{team_id}/{key}"
    # if its an external demo, or we're in debug mode, don't generate these
    if (
        organization.organization_type == Organization.OrganizationType.EXTERNAL_DEMO
        or settings.DEBUG
    ):
        return {"exists": False, "url": None}

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
