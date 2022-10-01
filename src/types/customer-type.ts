import { PlanDisplay } from "./plan-type";
import { SubscriptionType } from "./subscription-type";
export interface CustomerType {
  customer_name: string;
  billing_id?: string;
  balance?: string;
  customer_id: string;
}

export interface CustomerDetailType extends CustomerType {
  email: string;
  timeline: object;
  total_revenue_due: number;
  subscriptions: CustomerDetailSubscription[];
  billing_address: string;
}

export interface CustomerPlus extends CustomerType {
  subscriptions: CustomerSubscription[];
}
export interface CustomerTableItem extends CustomerPlus {
  total_revenue_due: number;
}

export interface CustomerTotal {
  customer_id: string;
  total_revenue_due: number;
}

interface CustomerSubscription {
  billing_plan_name: string;
  auto_renew: boolean;
  end_date: string;
}

export interface CustomerDetailSubscription extends CustomerSubscription {
  subscription_uid: string;
  start_date: string;
  status: string;
}
export interface CustomerSummary {
  customers: CustomerPlus[];
}
