from datetime import datetime
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.forms.models import model_to_dict
from metering_billing.models import Invoice
from metering_billing.serializers.serializer_utils import PlanUUIDField
from metering_billing.utils.enums import CHARGEABLE_ITEM_TYPE
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FONT_XL = 26
FONT_L = 24
FONT_M = 16
FONT_S = 14
FONT_XS = 12
FONT_XXS = 10

black01 = Color(0, 0, 0, alpha=0.1)

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
        s3.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        int(e.response["Error"]["Code"])
        return False


def transform_date(date: datetime) -> str:
    # Format the input datetime object as a string in the desired output format
    formatted_string = date.strftime("%d/%m/%Y")

    return formatted_string


def draw_logo(doc):
    doc.drawInlineImage("backend/metering_billing/logo.png", 565, 35)


def draw_hr(doc, vertical_offset):
    doc.setStrokeColor(black01)
    doc.setLineWidth(1)
    doc.line(75, vertical_offset, 550, vertical_offset)
    doc.setStrokeColor("black")


def draw_big_hr(doc, vertical_offset):
    doc.setStrokeColor(black01)
    doc.setLineWidth(1)
    doc.line(50, vertical_offset, 565, vertical_offset)
    doc.setStrokeColor("black")


def draw_vr(doc, x, y, offset):
    doc.setStrokeColor(black01)
    doc.setLineWidth(1)
    doc.line(x, y, x, y + offset)
    doc.setStrokeColor("black")


def write_invoice_title(doc):
    doc.setFont("Times-Roman", FONT_L)
    doc.drawString(25, 50, "Invoice")
    doc.setFont("Times-Roman", FONT_XXS)
    doc.drawString(470, 770, "Thank you for your buisness.")


def write_seller_details(
    doc, name, line1, city, state, country, postal_code, number, email
):
    if email is None:
        email = ""
    doc.setFont("Times-Bold", FONT_XS)
    doc.drawString(75, 130, name[:12] + "...")
    doc.setFont("Times-Roman", FONT_XXS)
    doc.drawString(75, 145, line1)
    doc.drawString(75, 160, f"{city} {state}, {postal_code}")
    doc.drawString(75, 175, country)
    doc.drawString(75, 190, number)
    doc.drawString(75, 205, email)


def write_customer_details(doc, name, line1, city, state, country, postal_code, email):
    if email is None:
        email = ""
    if name is None:
        name = ""
    doc.setFont("Times-Bold", FONT_M)
    doc.drawString(225, 130, "Billed To")
    doc.setFont("Times-Roman", FONT_XS)
    doc.drawString(225, 145, name)
    doc.drawString(225, 160, line1)
    doc.drawString(225, 175, f"{city} {state}, {postal_code}")
    doc.drawString(225, 190, country)
    doc.drawString(225, 205, email)


def write_invoice_details(doc, invoice_number, issue_date, due_date):
    doc.setFont("Times-Bold", FONT_XS)
    doc.drawString(400, 130, "Invoice Details")
    doc.setFont("Times-Roman", FONT_XXS)
    doc.drawString(400, 145, "Invoice No.")
    doc.drawString(465, 145, f"{invoice_number}")

    doc.drawString(400, 160, "Date Issued")
    doc.drawString(465, 160, f'{issue_date.replace("-", "/")}')

    doc.drawString(400, 175, "Due Date")
    if due_date:
        doc.drawString(465, 175, f'{due_date.replace("-", "/")}')
    else:
        doc.drawString(465, 175, f'{issue_date.replace("-", "/")}')
    doc.setFont("Times-Roman", FONT_XXS)

    doc.setFillColor(HexColor("#9CA3AF"))
    doc.drawString(25, 770, f"#{invoice_number}")


def write_summary_header(doc, start_date, end_date):
    doc.setFont("Times-Roman", 22)
    doc.setFillColor("black")
    doc.drawString(75, 255, "Summary")
    doc.setFont("Times-Roman", FONT_XXS)
    doc.setFillColor(HexColor("#9CA3AF"))
    doc.drawString(167, 255, f"{start_date} - {end_date}")
    doc.setFillColor("black")
    doc.setFont("Times-Roman", FONT_XS)
    doc.setFillColor(HexColor("#9CA3AF"))
    doc.drawString(75, 290, "Services")
    doc.drawString(475, 290, "Amount")
    doc.setFillColor("black")
    draw_hr(doc, 310)


def write_line_item_group(doc, name, amount, currency, line_item_start):
    title_offset = line_item_start + 20
    doc.setFont("Times-Roman", FONT_S)
    doc.drawString(75, title_offset, name)
    doc.drawString(475, title_offset, f'{currency}{"{:g}".format(float(amount))}')
    return line_item_start + 45


def write_line_item_headers(doc, line_item_start):
    offset = line_item_start + 5
    doc.setFont("Times-Roman", FONT_XXS)
    doc.setFillColor(HexColor("#9CA3AF"))
    doc.drawString(100, offset, "Item")
    doc.drawString(225, offset, "Dates")
    doc.drawString(350, offset, "Quantity")
    doc.drawString(412.5, offset, "Subtotal")
    doc.drawString(475, offset, "Billing Type")
    return line_item_start + 20


def write_line_item(
    doc,
    name,
    start_date,
    end_date,
    quantity,
    subtotal,
    currency_symbol,
    billing_type,
    line_item_start,
):
    doc.setFillColor("black")
    offset = line_item_start + 12
    doc.setFont("Times-Roman", FONT_XXS)

    # simple text wrap
    words = name.split()
    line = ""
    for word in words:
        w = doc.stringWidth(line + " " + word)
        if w > 100:
            doc.drawString(100, offset, line)
            offset += 11
            line = " " + word
        else:
            line += " " + word
    doc.drawString(100, offset, line)

    doc.drawString(
        225, offset, f'{start_date.replace("-", "/")} - {end_date.replace("-", "/")}'
    )

    if quantity:
        new_quantity = "{:g}".format(float(quantity))
        doc.drawString(350, offset, str(new_quantity))
    else:
        doc.drawString(350, offset, str(quantity))
    if subtotal:
        new_subtotal = "{:g}".format(float(subtotal))
        doc.drawString(412.5, offset, f"{currency_symbol}{str(new_subtotal)}")
    else:
        doc.drawString(412.5, offset, f"{currency_symbol}{str(subtotal)}")

    doc.drawString(475, offset, billing_type)

    draw_vr(doc, 90, line_item_start - 22, 35)

    return line_item_start + 35


def write_total(doc, currency_symbol, total, current_y):
    offset = current_y + 75
    doc.setFont("Times-Roman", FONT_XS)
    doc.drawString(80, offset, "TAX")
    doc.drawString(80, offset + 24, "Credits")
    doc.setFont("Times-Roman", FONT_M)
    doc.drawString(80, offset + 60, "Total")
    doc.drawString(475, offset + 60, f"{currency_symbol}{total}")
    draw_hr(doc, offset + 75)


def generate_invoice_pdf(
    invoice: Invoice,
    buffer,
):
    doc = canvas.Canvas(buffer, pagesize=letter, bottomup=0)

    customer = invoice.customer
    organization = invoice.organization
    subscription = invoice.subscription
    currency = invoice.currency
    line_items = invoice.line_items.all()
    write_invoice_title(doc)
    # draw_logo(doc)

    address = organization.properties.get("address")
    if address:
        write_seller_details(
            doc,
            organization.organization_name,
            address["line1"],
            address["city"],
            address["state"],
            address["country"],
            address["postal_code"],
            organization.phone,
            organization.email,
        )
    else:
        write_seller_details(
            doc,
            organization.organization_name,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )

    customer_address = customer.properties.get("address")
    if customer_address:
        write_customer_details(
            doc,
            customer.customer_name,
            customer_address["line1"],
            customer_address["city"],
            customer_address["state"],
            customer_address["country"],
            customer_address["postal_code"],
            customer.email,
        )
    else:
        write_customer_details(
            doc,
            customer.customer_name,
            "",
            "",
            "",
            "",
            "",
            customer.email,
        )

    if invoice.due_date:
        write_invoice_details(
            doc,
            invoice.invoice_number,
            transform_date(invoice.issue_date),
            transform_date(invoice.due_date),
        )
    else:
        write_invoice_details(
            doc,
            invoice.invoice_number,
            transform_date(invoice.issue_date),
            transform_date(invoice.issue_date),
        )

    draw_big_hr(doc, 200)

    write_summary_header(
        doc,
        transform_date(subscription.start_date),
        transform_date(subscription.end_date),
    )

    grouped_line_items = {}
    for line_item in line_items:
        sr = line_item.associated_subscription_record
        if sr is not None:
            plan_name = (
                line_item.associated_subscription_record.billing_plan.plan.plan_name
            )
            plan_id = PlanUUIDField().to_representation(
                line_item.associated_subscription_record.billing_plan.plan.plan_id
            )
            subscription_filters = list(
                (
                    line_item.associated_subscription_record.get_filters_dictionary()
                ).items()
            )
            if len(subscription_filters) > 0:
                subscription_filters = subscription_filters[0]
            else:
                subscription_filters = None
        else:
            plan_id = None
            subscription_filters = None
            plan_name = None
        key = (subscription_filters, plan_id, plan_name)
        if key not in grouped_line_items:
            grouped_line_items[key] = []

        # Add the line item to the list for the key
        grouped_line_items[key].append(line_item)

    line_item_start_y = 312
    taxes = []
    for group in grouped_line_items:
        amount = sum(
            model_to_dict(line_item)["subtotal"]
            for line_item in grouped_line_items[group]
        )
        pt1 = group[2]
        pt2 = group[0]
        if pt2 is not None:
            pt2 = pt2[0]
        pt3 = group[0]
        if pt3 is not None:
            pt3 = pt3[1]
        line_item_start_y = write_line_item_group(
            doc,
            f"{pt1} - {pt2} : {pt3} ",
            amount,
            currency.symbol,
            line_item_start_y,
        )
        line_item_start_y = write_line_item_headers(doc, line_item_start_y)

        line_item_count = 0
        for line_item_model in grouped_line_items[group]:
            if line_item_model.chargeable_item_type == CHARGEABLE_ITEM_TYPE.TAX:
                taxes.append(line_item_model)
                continue
            line_item_count += 1
            line_item = model_to_dict(line_item_model)
            line_item_start_y = write_line_item(
                doc,
                # "long name and this should wrap to somee",
                line_item["name"],
                transform_date(line_item["start_date"]),
                transform_date(line_item["end_date"]),
                line_item["quantity"],
                line_item["subtotal"],
                currency.symbol,
                line_item["billing_type"],
                line_item_start_y,
            )

            if line_item_start_y > 655:
                doc.showPage()
                line_item_start_y = 40

                doc.setFont("Times-Roman", FONT_XXS)
                invoice_number = invoice["invoice_number"]
                doc.setFillColor(HexColor("#9CA3AF"))
                doc.drawString(25, 770, f"#{invoice_number}")
                doc.setFillColor("black")
                doc.drawString(470, 770, "Thank you for your buisness.")

        draw_vr(doc, 90, line_item_start_y - 22, 5)
        draw_hr(doc, line_item_start_y)

    for tax_line_item in taxes:
        line_item = model_to_dict(tax_line_item)
        line_item_start_y = write_line_item(
            doc,
            line_item["name"],
            transform_date(line_item["start_date"]),
            transform_date(line_item["end_date"]),
            line_item["quantity"],
            line_item["subtotal"],
            currency.symbol,
            line_item["billing_type"],
            line_item_start_y,
        )
        if line_item_start_y > 655:
            doc.showPage()
            line_item_start_y = 40

            doc.setFont("Times-Roman", FONT_XXS)
            invoice_number = invoice["invoice_number"]
            doc.setFillColor(HexColor("#9CA3AF"))
            doc.drawString(25, 770, f"#{invoice_number}")
            doc.setFillColor("black")
            doc.drawString(470, 770, "Thank you for your buisness.")

    write_total(doc, currency.symbol, round(invoice.cost_due, 2), line_item_start_y)

    doc.save()

    if settings.DEBUG is False:
        try:
            # Upload the file to s3

            invoice_number = invoice.invoice_number
            organization_id = organization.organization_id
            customer_id = customer.customer_id
            team = organization.team
            team_id = team.team_id.hex

            bucket_name = "lotus-" + team_id

            if s3_bucket_exists(bucket_name):
                pass
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                )

            key = f"{organization_id}/{customer_id}/invoice_pdf_{invoice_number}.pdf"
            buffer.seek(0)
            s3.Bucket(bucket_name).upload_fileobj(buffer, key)

            s3.Object(bucket_name, key)

            # url = s3.generate_presigned_url(
            #     ClientMethod="get_object",
            #     Params={"Bucket": bucket_name, "Key": key},
            #     ExpiresIn=36000000,  # URL will expire in 1 hour
            # )
            # return url
        except Exception as e:
            print(e)
    # # else:
    # invoice_number = invoice["invoice_number"]
    # doc.save("image_files/invoice_pdf_" + invoice_number + ".pdf")
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

    bucket_name = "lotus-" + team_id

    key = f"{organization_id}/{customer_id}/invoice_pdf_{invoice_number}.pdf"

    if not s3_file_exists(bucket_name=bucket_name, key=key):
        generate_invoice_pdf(invoice, BytesIO())

    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=3600,  # URL will expire in 1 hour
    )
    return {"exists": True, "url": url}
