export interface InvoiceType {
  cost_due: string;
  cost_due_currency: string;
  id: number;
  issue_date: string;
  payment_status: string;
  line_items: LineItem[];
  customer: InvoiceCustomer;
}

interface InvoiceCustomer {
  customer_id: number;
  name: string;
}

interface InvoiceOrganization {
  company_name: string;
}

interface LineItem {
  components: object;
  flat_amount_due: number;
  total_amount_due: number;
  usage_amount_due: number;
}
