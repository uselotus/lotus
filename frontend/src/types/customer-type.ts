import { PlanDisplay } from "./plan-type";
import { SubscriptionType } from "./subscription-type";
import { BalanceAdjustments, InvoiceType} from "./invoice-type";

export interface CustomerType {
  customer_name: string;
  balance?: string;
  customer_id: string;
  email: string;
  payment_provider_id?: string;
  payment_provider?: string;
}

export interface CustomerDetailType extends CustomerType {
  email: string;
  timeline: object;
  total_amount_due: number;
  subscriptions: CustomerDetailSubscription[];
  billing_address: string;
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

export interface CustomerDetailSubscription extends CustomerSubscription {
  subscription_id: string;
  start_date: string;
  status: string;
}
export interface CustomerSummary {
  customers: CustomerPlus[];
}
