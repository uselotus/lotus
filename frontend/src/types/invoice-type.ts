import { LightweightCustomerType } from "./customer-type";
import { PricingUnit } from "./pricing-unit-type";

export interface InvoiceType {
  invoice_number: string;
  cost_due: number;
  currency: PricingUnit;
  issue_date: string;
  payment_status: "draft" | "paid" | "unpaid" | "voided";
  external_payment_obj_type: string;
  external_payment_obj_id: string;
  line_items: LineItem[];
  customer: LightweightCustomerType;
}

export interface DraftInvoiceType {
  invoices: IndividualDraftInvoiceType[];
}

export interface IndividualDraftInvoiceType {
  line_items: ExternalLineItem[];
  cost_due: number;
  issue_date: string;
  due_date: string;
  currency: {
    code: string;
    name: string;
    symbol: string;
  };
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
  plan: string; //TODO::: fix
  metadata: object;
  subscription_filters: { property_name: string; value: string }[];
}

export interface MarkInvoiceStatusAsPaid {
  invoice_number: string;
  payment_status: "paid" | "unpaid" | "voided";
}
