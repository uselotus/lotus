import logging
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from metering_billing.models import Invoice

from metering_billing.InvoiceToPDF import InvoicePDF


logger = logging.getLogger("django.server")

try:
    s3 = boto3.resource(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
except ClientError:
    pass


def s3_bucket_exists(bucket_name) -> bool:
    try:
        s3_client = boto3.client("s3")
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        int(e.response["Error"]["Code"])
        return False


def generate_invoice_pdf(invoice: Invoice, buffer):

    # init class
    inv = InvoicePDF(invoice, buffer)
    print("InvoicePDF", invoice)

    # build invoice (calls pdf.save())
    _ = inv.build(buffer)

    customer = invoice.customer
    organization = invoice.organization

    # If the organization is not an external demo organization
    if True and organization.organization_type != 3:
        try:
            # Upload the file to s3
            invoice_number = invoice.invoice_number
            organization_id = organization.organization_id.hex
            customer_id = customer.customer_id
            team = organization.team
            team_id = team.team_id.hex

            if settings.DEBUG:
                bucket_name = "dev-" + team_id
            else:
                bucket_name = "lotus-" + team_id

            if s3_bucket_exists(bucket_name):
                logger.debug("Bucket exists")
            else:
                s3.create_bucket(Bucket=bucket_name, ACL="private")
                logger.debug("Created bucket", bucket_name)

            key = f"{organization_id}/{customer_id}/invoice_pdf_{invoice_number}.pdf"
            buffer.seek(0)
            s3.Bucket(bucket_name).upload_fileobj(buffer, key)

            s3.Object(bucket_name, key)

        except Exception as e:
            print(e)

    return ""


def s3_file_exists(bucket_name, key):
    try:
        s3.Object(bucket_name, key).load()
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise
    else:
        return True


def get_invoice_presigned_url(invoice: Invoice):
    organization_id = invoice.organization.organization_id.hex
    team_id = invoice.organization.team.team_id.hex
    invoice_number = invoice.invoice_number

    customer_id = invoice.customer.customer_id

    if False:
        bucket_name = "dev-" + team_id
        return {"exists": False, "url": ""}

    else:
        bucket_name = "dev-" + team_id

        # bucket_name = "lotus-" + team_id
        key = f"{organization_id}/{customer_id}/invoice_pdf_{invoice_number}.pdf"

        if not s3_file_exists(bucket_name=bucket_name, key=key):
            generate_invoice_pdf(invoice, BytesIO())

        s3_client = boto3.client("s3")

        url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=3600,  # URL will expire in 1 hour
        )
    return {"exists": True, "url": url}
