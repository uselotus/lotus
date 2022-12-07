import { PlanDisplay, PlanVersionType } from "./plan-type";
import { SubscriptionType } from "./subscription-type";
import { BalanceAdjustments, InvoiceType } from "./invoice-type";
import { PricingUnit } from "./pricing-unit-type";

export interface CustomerType {
  customer_name: string;
  balance?: string;
  customer_id: string;
  email: string;
  payment_provider_id?: string;
  payment_provider?: string;
  default_currency?: PricingUnit;
  default_currency_code?: string;
}

export interface CustomerDetailType extends CustomerType {
  email: string;
  timeline: object;
  total_amount_due: number;
  subscription: CustomerDetailSubscription;
  billing_address: string;
  integrations: any;
  invoices: InvoiceType[];
  balance_adjustments: BalanceAdjustments[];
}

export interface CustomerPlus extends CustomerType {
  subscriptions: CustomerSubscription[];
}
export interface CustomerTableItem extends CustomerPlus {
  total_amount_due: number;
}

export interface CustomerTotal {
  customer_id: string;
  total_amount_due: number;
}

interface CustomerSubscription {
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
  customers: CustomerPlus[];
}
