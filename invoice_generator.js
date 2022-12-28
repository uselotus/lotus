import PDFDocument from 'pdfkit';

const FONT_XL = 26
const FONT_L = 24
const FONT_M = 16
const FONT_S = 14
const FONT_XS = 12
const FONT_XXS = 10

function draw_hr(doc, vertical_offset){
    doc
        .strokeColor('gray')
        .moveTo(75, doc.y + vertical_offset)
        .lineTo(550,doc.y + vertical_offset)
        .stroke()
        .strokeColor('black')
}

function write_invoice_title(doc){
    doc
        .font('Times-Bold', FONT_L)
        .text('Invoice', 50, 50);
}

function write_seller_details(doc, name, line1, city, state, country, postal_code,
                             number, email ){
    doc
        .font('Times-Bold', FONT_M)
        .text(`${name}`, 75, 125)
        .font('Times-Roman', FONT_XS)
        .text(`${line1}`)
        .text(`${city} ${state}, ${postal_code}`)
        .text(`${country}`)
        .text(`${number}`)
        .text(`${email}`)
}

function write_customer_details(doc, name, line1, city, state, country, postal_code, email ){
    doc
        .font('Times-Bold', FONT_M)
        .text('Billed To', 225, 125)
        .font('Times-Roman', FONT_XS)
        .text(`${name}`)
        .text(`${line1}`)
        .text(`${city} ${state}, ${postal_code}`)
        .text(`${country}`)
        .text(`${email}`)
}

function write_invoice_details(doc, invoice_number, issue_date, due_date){
    doc
        .font('Times-Bold', FONT_M)
        .text('Invoice Details', 375, 125)
        .font('Times-Roman', FONT_XS)
        .text(`Invoice No. ${invoice_number}`)
        .text(`Date Issued ${issue_date.replaceAll('-', '/')}`)
        .text(`Due Date ${due_date.replaceAll('-', '/')}`)
}

function write_summary_header(doc, start_date, end_date){
    doc
    .font('Times-Roman', FONT_XL)
    .text('Summary', 75, doc.y + 50)
    .font('Times-Roman', FONT_S)
    .fillColor('gray')
    .text(`${start_date.replaceAll('-', '/')}-${end_date.replaceAll('-', '/')}`, 200, doc.y - 22)
    .fillColor('black')
    .font('Times-Roman', FONT_S)
    .fillColor('gray')
    .text('Services', 75, doc.y + 25)
    .text('Quantity', 350, doc.y - 20)
    .text('Amount', 475, doc.y - 20)
    .fillColor('black')
    
    draw_hr(doc, 10)
}

function write_line_item(doc, name, start_date, end_date, quantity, 
                        subtotal, currency_symbol) {
    if (doc.y > 680 ){ 
        doc.addPage(); 
        doc.y = 40; 
    }
        
    let title_offset = doc.y + 25 // sets row height
    let datespan_offset = doc.y + 32 // centers quantity & subtotal
    doc
        .font('Times-Roman', FONT_S)
        .text( `${name}`, 75, title_offset)
        .fillColor('gray')
        .font('Times-Italic', FONT_XXS)
        .text( `${start_date.replaceAll('-', '/')}-${end_date.replaceAll('-', '/')}`, 75, doc.y)
        .font('Times-Roman', FONT_S)
        .fillColor('black')
        .text(`${quantity}`, 350, datespan_offset)
        .text(`${currency_symbol}${subtotal}`, 475, datespan_offset)
        .fillColor('black')
    draw_hr(doc, 10)
}

function write_total(doc, total){
    let offset = doc.y + 50 // sets row height
    doc
        .font('Times-Bold', FONT_S)
        .text( 'Total Due', 75, offset)
        .text(`${total}`, 475, offset)
        .fillColor('black')
}

function generate_invoice(doc, invoice_json){
    write_invoice_title(doc)
    write_seller_details(doc, invoice_json['seller']['name'], invoice_json['seller']['address']['line1'], 
                              invoice_json['seller']['address']['city'], invoice_json['seller']['address']['state'],
                              invoice_json['seller']['address']['country'], invoice_json['seller']['address']['postal_code'],
                              invoice_json['seller']['phone'], invoice_json['seller']['email'])

    write_customer_details(doc, invoice_json['customer']['customer_name'], invoice_json['customer']['address']['line1'], 
    invoice_json['customer']['address']['city'], invoice_json['customer']['address']['state'],
    invoice_json['customer']['address']['country'], invoice_json['customer']['address']['postal_code'],
    invoice_json['customer']['email'])

    write_invoice_details(doc, invoice_json['invoice_number'], invoice_json['issue_date'], invoice_json['due_date'])
    write_summary_header(doc,  invoice_json['start_date'], invoice_json['end_date'])
    
    for (const i in invoice_json['line_items']) {
        line_item = invoice_json['line_items'][i]
        write_line_item(doc, line_item['name'], line_item['start_date'], line_item['end_date'], 
                        line_item['quantity'], line_item['subtotal'],invoice_json['currency']['symbol'] )
      }
    write_total(doc, '' ,invoice_json['cost_due'])
}

let doc = new PDFDocument({size:'A4'});
let stream = doc.pipe(blobStream());
generate_invoice(doc, data)
doc.end();

stream.on('finish', function() {
  iframe.src = stream.toBlobURL('application/pdf');
});
