import logging
import os
from decimal import Decimal
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.forms.models import model_to_dict
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.rl_config import TTFSearchPath

from metering_billing.serializers.serializer_utils import PlanUUIDField
from metering_billing.utils import make_hashable
from metering_billing.utils.enums import CHARGEABLE_ITEM_TYPE

logger = logging.getLogger("django.server")

try:
    s3 = boto3.resource(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
except ClientError:
    pass

FONT_XL = 24
FONT_L = 22
FONT_M = 14
FONT_S = 12
FONT_XS = 10
FONT_XXS = 9

black01 = Color(0, 0, 0, alpha=0.1)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TTFSearchPath.append(str(BASE_DIR))

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

pdfmetrics.registerFont(TTFont("Alliance", "alliance.ttf"))
pdfmetrics.registerFont(TTFont("Alliance Bold", "alliance-bold.ttf"))

FONT_FAMILY = "Alliance"
FONT_FAMILY_BOLD = "Alliance Bold"


# generate a PDF invoice based on customers
# information.


def transform_date(date):
    """Transforms a datetime date into the correct format"""
    if type(date) == str:
        return date

    formatted_string = date.strftime("%d/%m/%Y")

    return formatted_string


class InvoicePDF:
    def __init__(self, invoice, buffer=None):
        """Takes an invoice and buffer (ie. name for output file)"""
        self.invoice = invoice
        self.buffer = buffer

    def fontSize(self, size, bold=False):
        """Helper Function: Change the font size"""

        if not bold:
            self.PDF.setFont(FONT_FAMILY, size)
        else:
            self.PDF.setFont(FONT_FAMILY_BOLD, size)

    def shortenStrings(self, string, length):
        """Shorten a string"""

        if not string:
            return ""

        if len(string) > length:
            return string[:length] + "..."

        return string

    def floor_string(self, string):
        """Like floor() in math, but for strings... sorta"""

        if string:
            return string

        return ""

    def draw_image(self):
        """Draws the logo image to the PDF"""
        self.PDF.saveState()
        self.PDF.scale(1, -1)
        # self.PDF.drawImage(
        #     LOGO, 490, -78, width=80, preserveAspectRatio=True, mask="auto"
        # )
        self.PDF.restoreState()

    def build(self, buffer=None) -> any:
        """Runs the functions to build the PDF and saves the result"""

        # init PDF
        if buffer:
            self.PDF = canvas.Canvas(buffer, pagesize=letter, bottomup=0)
        else:
            self.PDF = canvas.Canvas(self.buffer, pagesize=letter, bottomup=0)

        # run funcs

        self.add_title()
        self.draw_image()
        self.add_org_details()
        self.add_customer_details()
        self.draw_line(225)
        self.add_due_date()
        self.add_subscription()

        # save the pdf

        self.PDF.save()
        return self.PDF

    def add_summary_header(self):
        """Add's the summery header"""
        self.fontSize(22, bold=True)
        self.PDF.setFillColor("black")
        self.PDF.drawString(75, 260, "Summary")
        self.fontSize(FONT_XXS)
        self.PDF.setFillColor(HexColor("#9CA3AF"))
        # self.PDF.drawString(
        #     185,
        #     260,
        #     f"{self.invoice.subscription.start_date} - {self.invoice.subscription.end_date}",
        # )
        self.PDF.setFillColor("black")
        self.fontSize(FONT_XS)
        self.PDF.setFillColor(HexColor("#9CA3AF"))
        self.PDF.drawString(75, 290, "Services")
        self.PDF.drawString(475, 290, "Amount")
        self.PDF.setFillColor("black")
        self.draw_line(305)

    def write_line_item_group(self, name, amount, currency, line_item_start):
        """Draw a line item group"""
        self.fontSize(FONT_S)
        title_offset = line_item_start + 20
        self.PDF.drawString(75, title_offset, name)
        self.PDF.drawString(
            475, title_offset, f'{currency}{"{:g}".format(float(amount))}'
        )
        return line_item_start + 45

    def write_line_item(
        self,
        name,
        start_date,
        end_date,
        quantity,
        amount,
        currency_symbol,
        billing_type,
        line_item_start,
    ):
        """Draw a line item"""
        self.PDF.setFillColor("black")
        offset = line_item_start + 12
        self.fontSize(FONT_XXS)

        # simple text wrap
        words = name.split()
        line = ""
        for word in words:
            w = self.PDF.stringWidth(line + " " + word)
            if w > 100:
                self.PDF.drawString(100, offset, line)
                offset += 11
                line = " " + word
            else:
                line += " " + word
        self.PDF.drawString(100, offset, line)

        if start_date == end_date:
            start_date = transform_date(start_date)
            date_string = str(start_date.replace("-", "/"))
        else:
            start_date = transform_date(start_date)
            end_date = transform_date(end_date)
            date_string = (
                f'{start_date.replace("-", "/")} - {end_date.replace("-", "/")}'
            )
        self.PDF.drawString(225, offset, date_string)

        if quantity is not None:
            new_quantity = "{:g}".format(float(quantity))
            self.PDF.drawString(350, offset, str(new_quantity))
        else:
            self.PDF.drawString(350, offset, "")
        if amount:
            new_amount = "{:g}".format(float(amount))
            self.PDF.drawString(412.5, offset, f"{currency_symbol}{str(new_amount)}")
        else:
            self.PDF.drawString(412.5, offset, f"{currency_symbol}{str(amount)}")

        self.PDF.drawString(475, offset, billing_type)

        self.PDF.setStrokeColor(black01)
        self.PDF.setLineWidth(1)
        self.PDF.line(90, line_item_start - 22, 90, (line_item_start - 22) + 35)
        self.PDF.setStrokeColor("black")

        return line_item_start + 35

    def write_line_item_headers(self, line_item_start):
        """Draw the headers for line items"""
        offset = line_item_start + 5
        self.fontSize(FONT_XXS)

        self.PDF.setFillColor(HexColor("#9CA3AF"))
        self.PDF.drawString(100, offset, "Item")
        self.PDF.drawString(225, offset, "Dates")
        self.PDF.drawString(350, offset, "Quantity")
        self.PDF.drawString(412.5, offset, "amount")
        self.PDF.drawString(475, offset, "Billing Type")
        return line_item_start + 20

    def draw_line(self, x):
        """Draws a line at a certain x cord"""
        self.PDF.setStrokeColor(black01)
        self.PDF.setLineWidth(1)
        self.PDF.line(75, x, 550, x)
        self.PDF.setStrokeColor("black")

    def add_title(self):
        """Add a title to the PDF"""
        self.fontSize(FONT_L, bold=True)
        self.PDF.drawString(25, 50, "Invoice")
        self.fontSize(FONT_XXS)
        self.PDF.drawString(470, 770, "Thank you for your buisness.")

        self.PDF.saveState()
        self.PDF.scale(1, -1)
        # self.PDF.drawImage(LOGO, 470, 30, mask="auto")
        self.PDF.restoreState()

    def add_org_details(self):
        """Add the Organization/Seller Details"""

        org = self.invoice.organization
        addr = org.address

        self.fontSize(FONT_S, bold=True)
        self.PDF.drawString(
            75, 127, self.shortenStrings(self.floor_string(org.organization_name), 18)
        )

        self.fontSize(FONT_XXS)

        x = 160

        if addr:
            self.PDF.drawString(75, 145, self.floor_string(addr.line1))

            if addr.city and addr.state and addr.postal_code:
                self.PDF.drawString(
                    75, x, f"{addr.city}, {addr.state}, {addr.postal_code}"
                )
                x += 15

            if addr.country:
                self.PDF.drawString(75, x, self.shortenStrings(addr.country, 18))
                x += 15

        self.PDF.drawString(
            75, x, self.shortenStrings(self.floor_string(org.email), 18)
        )

    def add_customer_details(self):
        """Add the customers details"""

        customer = self.invoice.customer
        addr = customer.get_billing_address()

        self.fontSize(FONT_S, bold=True)
        self.PDF.drawString(250, 127, "Billed To")

        self.fontSize(FONT_XXS)
        self.PDF.drawString(
            250, 145, self.shortenStrings(self.floor_string(customer.customer_name), 18)
        )

        x = 175

        if addr:
            self.PDF.drawString(250, 160, self.floor_string(addr.line1))

            if addr.city and addr.state and addr.postal_code:
                self.PDF.drawString(
                    250, x, f"{addr.city}, {addr.state}, {addr.postal_code}"
                )
                x += 15

            if addr.country:
                self.PDF.drawString(250, x, self.shortenStrings(addr.country, 18))
                x += 15

        self.PDF.drawString(
            250, x, self.shortenStrings(self.floor_string(customer.email), 18)
        )

    def add_due_date(self):
        """Add Due Date"""

        self.fontSize(FONT_S, bold=True)
        self.PDF.drawString(400, 127, "Invoice Details")

        self.fontSize(FONT_XXS)
        self.PDF.drawString(400, 145, "Invoice No.")
        self.PDF.drawString(465, 145, f"{self.invoice.invoice_number}")

        self.PDF.drawString(400, 160, "Date Issued")
        self.PDF.drawString(465, 160, f'{self.invoice.issue_date.strftime("%m/%d/%Y")}')

        self.PDF.drawString(400, 175, "Due Date")
        if self.invoice.due_date:
            self.PDF.drawString(
                465,
                175,
                f'{self.floor_string(self.invoice.due_date.strftime("%m/%d/%Y"))}',
            )
        else:
            self.PDF.drawString(
                465,
                175,
                "N/A",
            )

        self.PDF.setFillColor(HexColor("#9CA3AF"))
        self.PDF.drawString(25, 770, f"#{self.invoice.invoice_number}")

    def get_grouped_line_items(self):
        """Get grouped line items"""

        grouped_line_items = {}
        for line_item in self.invoice.line_items.all():
            sub_record = line_item.associated_subscription_record
            if sub_record is not None:
                plan_name = sub_record.billing_plan.plan.plan_name
                plan_id = PlanUUIDField().to_representation(
                    sub_record.billing_plan.plan.plan_id
                )
                sub_filters = list(sub_record.get_filters_dictionary().items())

                sub_filters = sub_filters if sub_filters else None

            else:
                plan_id, sub_filters, plan_name = None, None, None

            key = make_hashable([sub_filters, plan_id, plan_name])

            if key not in grouped_line_items:
                grouped_line_items[key] = []

            grouped_line_items[key].append(line_item)

        return grouped_line_items

    def write_total(
        self,
        currency_symbol,
        total,
        current_y,
        total_tax,
        total_credits,
        total_discount,
    ):
        offset = current_y + 75
        self.fontSize(FONT_XS)
        self.PDF.drawString(80, offset, "TAX")
        self.PDF.drawString(475, offset, f"{currency_symbol}{total_tax}")

        if total_credits > 0:
            self.PDF.drawString(80, offset + 24, "Credits")
            self.PDF.drawString(475, offset + 24, f"{currency_symbol}{total_credits}")

        if total_discount > 0:
            self.PDF.drawString(80, offset + 36, "Plan Discounts")
            self.PDF.drawString(475, offset + 36, f"{currency_symbol}{total_discount}")

        self.fontSize(FONT_M, bold=True)
        self.PDF.drawString(80, offset + 60, "Total")
        self.PDF.drawString(475, offset + 60, f"{currency_symbol}{total}")
        self.draw_line(offset + 80)

    def add_subscription(self):
        """Add Subscription data"""

        subscription_records = self.invoice.subscription_records

        if subscription_records:
            self.add_summary_header()
            pass

        grouped_line_items = self.get_grouped_line_items()

        line_item_start_y = 312
        tax_line_items = []
        tax_within_line_items = Decimal(0)
        consumed_credits = []
        total_discounts = Decimal(0)
        for group in grouped_line_items:
            amount = sum(
                model_to_dict(line_item)["amount"]
                for line_item in grouped_line_items[group]
                if line_item.chargeable_item_type != CHARGEABLE_ITEM_TYPE.TAX
            )
            # Subscription title
            pt1 = group[2]
            # Subscription filter
            subscription_filters = group[0]
            if (
                subscription_filters is not None
                and len(subscription_filters) > 0
                and subscription_filters[0] is not None
            ):
                pt2 = subscription_filters[0][0]
                pt3 = subscription_filters[0][1]
            else:
                pt2 = None
                pt3 = None

            if not pt2 and not pt3 and pt1:
                subscription_title = pt1
            # If there is no plan name
            elif not pt1:
                subscription_title = "Credit"
            else:
                subscription_title = f"{pt1} - {pt2} - {pt3}"
            line_item_start_y = self.write_line_item_group(
                subscription_title,
                amount.quantize(Decimal("0.00")),
                self.invoice.currency.symbol,
                line_item_start_y,
            )
            line_item_start_y = self.write_line_item_headers(line_item_start_y)

            line_item_count = 0
            for line_item_model in grouped_line_items[group]:
                if line_item_model.chargeable_item_type == CHARGEABLE_ITEM_TYPE.TAX:
                    tax_line_items.append(line_item_model)
                    continue
                if (
                    line_item_model.chargeable_item_type
                    == CHARGEABLE_ITEM_TYPE.CUSTOMER_ADJUSTMENT
                ):
                    consumed_credits.append(line_item_model)
                    continue
                line_item_count += 1
                line_item = model_to_dict(line_item_model)
                line_item_start_y = self.write_line_item(
                    line_item["name"],
                    line_item["start_date"],
                    line_item["end_date"],
                    line_item["quantity"].normalize()
                    if isinstance(line_item["quantity"], Decimal)
                    else line_item["quantity"],
                    line_item["base"].normalize(),
                    self.invoice.currency.symbol,
                    line_item["billing_type"],
                    line_item_start_y,
                )
                for adjustment in line_item["adjustments"]:
                    if adjustment["adjustment_type"] == "sales_tax":
                        tax_within_line_items += Decimal(adjustment["amount"])
                    if adjustment["adjustment_type"] == "plan_adjustment":
                        total_discounts += Decimal(adjustment["amount"])

                if line_item_start_y > 655:
                    self.PDF.showPage()
                    line_item_start_y = 40
                    self.PDF.setFont("Times-Roman", FONT_XXS)
                    invoice_number = self.invoice.invoice_number
                    self.PDF.setFillColor(HexColor("#9CA3AF"))
                    self.PDF.drawString(25, 770, f"#{invoice_number}")
                    self.PDF.setFillColor("black")
                    self.PDF.drawString(470, 770, "Thank you for your buisness.")

            self.PDF.setStrokeColor(black01)
            self.PDF.setLineWidth(1)
            self.PDF.line(90, line_item_start_y - 22, 90, (line_item_start_y - 22) + 5)
            self.PDF.setStrokeColor("black")
            self.draw_line(line_item_start_y)

        total_tax = Decimal(0) + tax_within_line_items
        for tax_line_item in tax_line_items:
            line_item = model_to_dict(tax_line_item)
            # line_item_start_y = write_line_item(
            #     doc,
            #     line_item["name"],
            #     transform_date(line_item["start_date"]),
            #     transform_date(line_item["end_date"]),
            #     line_item["quantity"],
            #     line_item["amount"],
            #     currency.symbol,
            #     line_item["billing_type"],
            #     line_item_start_y,
            # )
            # if line_item_start_y > 655:
            #     doc.showPage()
            #     line_item_start_y = 40

            #     doc.setFont("Times-Roman", FONT_XXS)
            #     invoice_number = invoice["invoice_number"]
            #     doc.setFillColor(HexColor("#9CA3AF"))
            #     doc.drawString(25, 770, f"#{invoice_number}")
            #     doc.setFillColor("black")
            #     doc.drawString(470, 770, "Thank you for your buisness.")
            total_tax += line_item["amount"]
        total_credits = Decimal(0)
        for credit_line_item in consumed_credits:
            line_item = model_to_dict(credit_line_item)
            total_credits += line_item["amount"]

        self.write_total(
            self.invoice.currency.symbol,
            round(self.invoice.amount, 2),
            line_item_start_y,
            total_tax.quantize(Decimal("0.00")),
            total_credits.quantize(Decimal("0.00")),
            total_discounts.quantize(Decimal("0.00")),
        )


def get_invoice_pdf_key(invoice):
    organization_id = invoice.organization.organization_id.hex
    customer_id = invoice.customer.customer_id
    invoice_number = invoice.invoice_number
    key = f"{organization_id}/{customer_id}/invoice_pdf_{invoice_number}.pdf"
    return key


def get_invoice_pdf_bucket_name(debug, team_id):
    bucket_name = "lotus-invoice-pdfs-2f7d6d16"
    if debug:
        bucket_name = "dev-" + bucket_name
    else:
        bucket_name = "lotus-" + team_id
    return bucket_name


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


def s3_bucket_exists(bucket_name) -> bool:
    try:
        s3_client = boto3.client("s3")
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        int(e.response["Error"]["Code"])
        return False


def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    # init class
    inv = InvoicePDF(invoice, buffer)

    # build invoice (calls pdf.save())
    _ = inv.build(buffer)

    return buffer


def upload_invoice_pdf_to_s3(invoice, team_id, bucket_name):
    try:
        key = get_invoice_pdf_key(invoice)
        buffer = generate_invoice_pdf(invoice)

        if s3_bucket_exists(bucket_name):
            logger.debug("Bucket exists")
        else:
            s3.create_bucket(Bucket=bucket_name, ACL="private")
            logger.debug("Created bucket", bucket_name)

        buffer.seek(0)
        s3.Bucket(bucket_name).upload_fileobj(buffer, key)

        s3.Object(bucket_name, key)

    except Exception as e:
        print(e)

    return key


def get_invoice_presigned_url(invoice):
    debug = settings.DEBUG
    team_id = invoice.organization.team.team_id.hex

    bucket_name = get_invoice_pdf_bucket_name(debug, team_id)
    key = get_invoice_pdf_key(invoice)

    if not s3_file_exists(bucket_name=bucket_name, key=key):
        upload_invoice_pdf_to_s3(invoice, team_id, bucket_name)

    s3_client = boto3.client("s3")

    url = s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=3600,  # URL will expire in 1 hour
    )
    return {"exists": True, "url": url}
