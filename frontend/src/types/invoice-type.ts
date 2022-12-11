import { CustomerType } from "./customer-type";
import { PricingUnit } from "./pricing-unit-type";

export interface InvoiceType {
  cost_due: string;
  cost_due_currency: string;
  id: string;
  issue_date: string;
  payment_status: string;
  line_items: LineItem[];
  customer: InvoiceCustomer;
  external_payment_obj_type: string;
}

export interface DraftInvoiceType {
  invoice: DraftInvoiceType2;
}
export interface DraftInvoiceType2 {
  line_items: ExternalLineItem[];
  cost_due: number;
  customer: CustomerType;
  currency: {
    code: string;
    name: string;
    symbol: string;
  };
  cust_connected_to_payment_provider: boolean;
  org_connected_to_cust_payment_provider: boolean;
  subscription: {
    end_date: string;
    start_date: string;
    status: string;
  };
}

export interface BalanceAdjustments {
  amount: number;
  amount_currency: string;
  description: string;
  created: string;
  effective_at: string;
  expires_at: string;
  adjustment_id: string;
  customer_id: string;
  parent_adjustment_id: string;
  pricing_unit: PricingUnit;
  status: "active" | "inactive";
}

interface InvoiceCustomer {
  customer_id: number;
  name: string;
}

interface InvoiceOrganization {
  company_name: string;
}

export interface ExternalLineItem {
  end_date: string;
  plan_name: string;
  start_date: string;
  subtotal: number;
  subscription_filters?: { property_name: string; value: string }[];
  sub_items: LineItem[];
}

export interface LineItem {
  name: string;
  start_date: string;
  end_date: string;
  quantity: number;
  subtotal: number;
  billing_type: string;
  plan_version_id: string;
  metadata?: any;
  subscription_filters?: { property_name: string; value: string }[];
}

export interface MarkInvoiceStatusAsPaid {
  invoice_number: string;
  payment_status: "paid" | "unpaid" | "voided";
}
