import { PlanDisplay, PlanVersionType } from "./plan-type";
import { SubscriptionType } from "./subscription-type";
import { BalanceAdjustments, InvoiceType } from "./invoice-type";
import { PricingUnit } from "./pricing-unit-type";

export interface CustomerType {
  customer_id: string;
  email: string;
  name: string;
  customer_name: string;
  invoices: InvoiceType[];
  total_amount_due: number;
  subscriptions: SubscriptionType[];
  integrations: object;
  default_currency: PricingUnit;
}

export interface LightweightCustomerType
  extends Omit<
    CustomerType,
    | "invoices"
    | "subscriptions"
    | "default_currency"
    | "total_amount_due"
    | "integrations"
  > {}

export interface CustomerCreateType
  extends Omit<
    CustomerType,
    "invoices" | "subscriptions" | "default_currency" | "customer_name"
  > {
  customer_name?: string;
  payment_provider?: string;
  payment_provider_id?: string;
  properties?: { [key: string]: string };
  default_currency_code?: string;
}

export interface CustomerTableItem extends CustomerType {
  total_amount_due: number;
}

export interface CustomerTableItem extends CustomerType {
  total_amount_due: number;
}

export interface CustomerTotal {
  customer_id: string;
  total_amount_due: number;
}

export interface CustomerSubscription {
  billing_plan_name: string;
  auto_renew: boolean;
  end_date: string;
  plan_version: number;
}

export interface DetailPlan {
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  is_new: boolean;
  subscription_filters: {
    value: string;
    property_name: string;
  }[];
  status: string;
  plan_detail: PlanVersionType;
}

export interface CustomerDetailSubscription extends CustomerSubscription {
  subscription_id: string;
  start_date: string;
  billing_cadence: "monthly" | "quarterly" | "yearly";
  plans: DetailPlan[];
  status: string;
}

export interface CustomerSummary {
  customer_id: string;
  customer_name: string;
  subscriptions: LightweightSubscription[];
}

export interface LightweightSubscription {
  billing_plan_name: string;
  plan_version: number;
  end_date: string;
  auto_renew: boolean;
}
