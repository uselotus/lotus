import boto3
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import os



FONT_XL = 26
FONT_L = 24
FONT_M = 16 
FONT_S = 14
FONT_XS = 12
FONT_XXS = 10

def draw_hr(doc, vertical_offset):
    doc.setStrokeColor('gray')
    doc.setLineWidth(1)
    doc.line(75, vertical_offset, 550, vertical_offset)
    doc.setStrokeColor('black')

def write_invoice_title(doc):
    doc.setFont('Times-Bold', FONT_L)
    doc.drawString(50, 50, 'Invoice')

def write_seller_details(doc, name, line1, city, state, country, postal_code,
                             number, email ):
    doc.setFont('Times-Bold', FONT_M)
    doc.drawString(75, 130, name)
    doc.setFont('Times-Roman', FONT_XS)
    doc.drawString(75, 145, line1)
    doc.drawString(75, 160, f'{city} {state}, {postal_code}')
    doc.drawString(75, 175, country)
    doc.drawString(75, 190, number)
    doc.drawString(75, 205, email)

def write_customer_details(doc, name, line1, city, state, country, postal_code, email ):
    doc.setFont('Times-Bold', FONT_M)
    doc.drawString(225, 130, 'Billed To')
    doc.setFont('Times-Roman', FONT_XS)
    doc.drawString(225, 145, name)
    doc.drawString(225, 160, line1)
    doc.drawString(225, 175, f'{city} {state}, {postal_code}')
    doc.drawString(225, 190, country)
    doc.drawString(225, 205, email)

def write_invoice_details(doc, invoice_number, issue_date, due_date):
    doc.setFont('Times-Bold', FONT_M)
    doc.drawString(375, 130, 'Invoice Details')
    doc.setFont('Times-Roman', FONT_XS)
    doc.drawString(375, 145, f'Invoice No. {invoice_number}')
    doc.drawString(375, 160, f'Date Issued {issue_date.replace("-", "/")}')
    doc.drawString(375, 175, f'Due Date {due_date.replace("-", "/")}')

def write_summary_header(doc, start_date, end_date):
    doc.setFont('Times-Roman', FONT_XL)
    doc.drawString(75, 255, 'Summary')
    doc.setFont('Times-Roman', FONT_S)
    doc.setFillColor('gray')
    doc.drawString(200, 253.5, f'{start_date.replace("-", "/")} - {end_date.replace("-", "/")}')
    doc.setFillColor('black')
    doc.setFont('Times-Roman', FONT_S)
    doc.setFillColor('gray')
    doc.drawString(75, 280, 'Services')
    doc.drawString(350, 280, 'Quantity')
    doc.drawString(475, 280, 'Amount')
    doc.setFillColor('black')
    draw_hr(doc, 290)

def write_line_item(doc, name, start_date, end_date, quantity, 
                    subtotal, currency_symbol, line_item_start):
    title_offset = line_item_start + 20
    datespan_offset = line_item_start + 27
    doc.setFont('Times-Roman', FONT_S)
    doc.drawString(75, title_offset, name)
    doc.setFillColor('gray')
    doc.setFont('Times-Italic', FONT_XXS)
    doc.drawString(75, line_item_start + 35, f'{start_date.replace("-", "/")} - {end_date.replace("-", "/")}')
    doc.setFont('Times-Roman', FONT_S)
    doc.setFillColor('black')
    doc.drawString(350, datespan_offset, str(quantity))
    doc.drawString(475, datespan_offset, f'{currency_symbol}{str(subtotal)}')
    doc.setFillColor('black')
    draw_hr(doc, line_item_start + 45)
    return line_item_start + 45

def write_total(doc, currency_symbol, total, current_y):
    offset = current_y+ 50
    doc.setFont('Times-Roman', FONT_S)
    doc.drawString(75, offset, 'Toal Due')
    doc.drawString(475, offset, f'{currency_symbol}{total}')

def generate_invoice_pdf(invoice, buffer):
    doc = canvas.Canvas(buffer)

    write_invoice_title(doc)
    write_seller_details(doc, invoice['seller']['name'], invoice['seller']['address']['line1'], 
                              invoice['seller']['address']['city'], invoice['seller']['address']['state'],
                              invoice['seller']['address']['country'], invoice['seller']['address']['postal_code'],
                              invoice['seller']['phone'], invoice['seller']['email'])

    write_customer_details(doc, invoice['customer']['customer_name'], invoice['customer']['address']['line1'], 
    invoice['customer']['address']['city'], invoice['customer']['address']['state'],
    invoice['customer']['address']['country'], invoice['customer']['address']['postal_code'],
    invoice['customer']['email'])

    write_invoice_details(doc, invoice['invoice_number'], invoice['issue_date'], invoice['due_date'])
    write_summary_header(doc,  invoice['start_date'], invoice['end_date'])
    
    line_item_start_y = 290
    for line_item in invoice['line_items']:
        line_item_start_y = write_line_item(doc, line_item['name'], line_item['start_date'], line_item['end_date'], 
                        line_item['quantity'], line_item['subtotal'],invoice['currency']['symbol'], line_item_start_y)
        if line_item_start_y > 680:
            doc.showPage()
            line_item_start_y = 40
    
    write_total(doc, invoice['currency']['symbol'], invoice['cost_due'], line_item_start_y)

    doc.save()

    #Upload the file to s3
    s3 = boto3.resource(
        's3',
        aws_access_key_id= os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key= os.environ['AWS_SECRET_ACCESS_KEY']
    )
    invoice_number = invoice['invoice_number']
    buffer.seek(0)
    s3.Bucket('BUCKET_NAME_HERE').upload_fileobj(buffer, f'invoice_pdf_{invoice_number}')

    return buffer


    