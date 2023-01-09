import os
from datetime import datetime
from io import BytesIO

import boto3
from django.conf import settings
from django.forms.models import model_to_dict
from metering_billing.utils.enums import CHARGEABLE_ITEM_TYPE
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_XL = 26
FONT_L = 24
FONT_M = 16
FONT_S = 14
FONT_XS = 12
FONT_XXS = 10


def transform_date(date: datetime) -> str:
    # Format the input datetime object as a string in the desired output format
    formatted_string = date.strftime("%d/%m/%Y")

    return formatted_string


def draw_hr(doc, vertical_offset):
    doc.setStrokeColor("gray")
    doc.setLineWidth(1)
    doc.line(75, vertical_offset, 550, vertical_offset)
    doc.setStrokeColor("black")


def write_invoice_title(doc):
    doc.setFont("Times-Bold", FONT_L)
    doc.drawString(50, 50, "Invoice")


def write_seller_details(
    doc, name, line1, city, state, country, postal_code, number, email
):
    if email is None:
        email = ""
    doc.setFont("Times-Bold", FONT_M)
    doc.drawString(75, 130, name[:12] + "...")
    doc.setFont("Times-Roman", FONT_XS)
    doc.drawString(75, 145, line1)
    doc.drawString(75, 160, f"{city} {state}, {postal_code}")
    doc.drawString(75, 175, country)
    doc.drawString(75, 190, number)
    doc.drawString(75, 205, email)


def write_customer_details(doc, name, line1, city, state, country, postal_code, email):
    if email is None:
        email = ""
    doc.setFont("Times-Bold", FONT_M)
    doc.drawString(225, 130, "Billed To")
    doc.setFont("Times-Roman", FONT_XS)
    doc.drawString(225, 145, name)
    doc.drawString(225, 160, line1)
    doc.drawString(225, 175, f"{city} {state}, {postal_code}")
    doc.drawString(225, 190, country)
    doc.drawString(225, 205, email)


def write_invoice_details(doc, invoice_number, issue_date, due_date):
    doc.setFont("Times-Bold", FONT_M)
    doc.drawString(375, 130, "Invoice Details")
    doc.setFont("Times-Roman", FONT_XS)
    doc.drawString(375, 145, f"Invoice No. {invoice_number}")
    doc.drawString(375, 160, f'Date Issued {issue_date.replace("-", "/")}')
    if due_date:
        doc.drawString(375, 175, f'Due Date {due_date.replace("-", "/")}')
    else:
        doc.drawString(375, 175, f'Due Date {issue_date.replace("-", "/")}')


def write_summary_header(doc):
    doc.setFont("Times-Roman", FONT_L)
    doc.drawString(75, 255, "Summary")
    doc.setFont("Times-Roman", FONT_S)
    doc.setFillColor("gray")
    # doc.drawString(
    #     200, 253.5, f'{start_date.replace("-", "/")} - {end_date.replace("-", "/")}'
    # )
    doc.setFillColor("black")
    doc.setFont("Times-Roman", FONT_S)
    doc.setFillColor("gray")
    doc.drawString(75, 280, "Services")
    doc.drawString(350, 280, "Quantity")
    doc.drawString(475, 280, "Amount")
    doc.setFillColor("black")
    draw_hr(doc, 290)


def write_line_item(
    doc,
    name,
    start_date,
    end_date,
    quantity,
    subtotal,
    currency_symbol,
    line_item_start,
):
    title_offset = line_item_start + 20
    datespan_offset = line_item_start + 27
    doc.setFont("Times-Roman", FONT_S)
    doc.drawString(75, title_offset, name)
    doc.setFillColor("gray")
    doc.setFont("Times-Italic", FONT_XXS)
    doc.drawString(
        75,
        line_item_start + 35,
        f'{start_date.replace("-", "/")} - {end_date.replace("-", "/")}',
    )
    doc.setFont("Times-Roman", FONT_S)
    doc.setFillColor("black")
    if quantity:
        new_quantity = "{:g}".format(float(quantity))
        doc.drawString(350, datespan_offset, str(new_quantity))
    else:
        doc.drawString(350, datespan_offset, str(quantity))
    if subtotal:
        new_subtotal = "{:g}".format(float(subtotal))
        doc.drawString(475, datespan_offset, f"{currency_symbol}{str(new_subtotal)}")
    else:
        doc.drawString(475, datespan_offset, f"{currency_symbol}{str(subtotal)}")
    doc.setFillColor("black")
    draw_hr(doc, line_item_start + 45)
    return line_item_start + 45


def write_total(doc, currency_symbol, total, current_y):
    offset = current_y + 50
    doc.setFont("Times-Roman", FONT_S)
    doc.drawString(75, offset, "Total Due")
    doc.drawString(475, offset, f"{currency_symbol}{total}")


def generate_invoice_pdf(invoice_model, organization, customer, line_items, buffer):
    doc = canvas.Canvas(buffer, pagesize=letter, bottomup=0)

    invoice = model_to_dict(invoice_model)
    currency = model_to_dict(invoice_model.currency)

    write_invoice_title(doc)

    address = organization["properties"].get("address")
    if address:
        write_seller_details(
            doc,
            organization["company_name"],
            organization["properties"]["address"]["line1"],
            organization["properties"]["city"],
            organization["properties"]["state"],
            organization["properties"]["address"]["country"],
            organization["properties"]["address"]["postal_code"],
            organization["phone"],
            organization["email"],
        )
    else:
        write_seller_details(
            doc,
            organization["company_name"],
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )

    customer_address = customer["properties"].get("address")
    if customer_address:
        write_customer_details(
            doc,
            customer["customer_name"],
            customer["properties"]["address"]["line1"],
            customer["properties"]["address"]["city"],
            customer["properties"]["address"]["state"],
            customer["properties"]["address"]["country"],
            customer["properties"]["address"]["postal_code"],
            customer["email"],
        )
    else:
        write_customer_details(
            doc,
            customer["customer_name"],
            "",
            "",
            "",
            "",
            "",
            customer["email"],
        )

    if invoice["due_date"]:
        write_invoice_details(
            doc,
            invoice["invoice_number"],
            transform_date(invoice["issue_date"]),
            transform_date(invoice["due_date"]),
        )
    else:
        write_invoice_details(
            doc,
            invoice["invoice_number"],
            transform_date(invoice["issue_date"]),
            transform_date(invoice["issue_date"]),
        )
    write_summary_header(doc)

    grouped_line_items = {}
    for line_item in line_items:
        sr = line_item.associated_subscription_record
        if sr is not None:
            plan_id = line_item.associated_subscription_record.billing_plan.id
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
        key = (subscription_filters, plan_id)
        if key not in grouped_line_items:
            grouped_line_items[key] = []

        # Add the line item to the list for the key
        grouped_line_items[key].append(line_item)

    line_item_start_y = 290
    taxes = []
    for group in grouped_line_items:
        for line_item_model in grouped_line_items[group]:
            if line_item_model.chargeable_item_type == CHARGEABLE_ITEM_TYPE.TAX:
                taxes.append(line_item_model)
                continue
            line_item = model_to_dict(line_item_model)
            line_item_start_y = write_line_item(
                doc,
                line_item["name"],
                transform_date(line_item["start_date"]),
                transform_date(line_item["end_date"]),
                line_item["quantity"],
                line_item["subtotal"],
                currency["symbol"],
                line_item_start_y,
            )
            if line_item_start_y > 680:
                doc.showPage()
                line_item_start_y = 40

    for tax_line_item in taxes:
        line_item = model_to_dict(tax_line_item)
        line_item_start_y = write_line_item(
            doc,
            line_item["name"],
            transform_date(line_item["start_date"]),
            transform_date(line_item["end_date"]),
            line_item["quantity"],
            line_item["subtotal"],
            currency["symbol"],
            line_item_start_y,
        )
        if line_item_start_y > 680:
            doc.showPage()
            line_item_start_y = 40
    write_total(
        doc, currency["symbol"], round(invoice["cost_due"], 2), line_item_start_y
    )

    doc.save()

    # if settings.DEBUG is False:
    try:
        # Upload the file to s3
        s3 = boto3.resource(
            "s3",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        invoice_number = invoice["invoice_number"]
        organization_id = invoice["organization"]
        customer_id = customer["customer_id"]
        bucket_name = os.environ["AWS_S3_INVOICE_BUCKET"]
        key = f"{organization_id}/{customer_id}/invoice_pdf_{invoice_number}.pdf"
        buffer.seek(0)
        s3.Bucket(bucket_name).upload_fileobj(buffer, key)

        s3_object = s3.Object(bucket_name, key)

        s3 = boto3.client("s3")

        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=3600,  # URL will expire in 1 hour
        )
        return url
    except Exception as e:
        print(e)
    # # else:
    # invoice_number = invoice["invoice_number"]
    # doc.save("image_files/invoice_pdf_" + invoice_number + ".pdf")
    return ""
