import { PlanDisplay } from "./plan-type";
import { SubscriptionType } from "./subscription-type";
export interface CustomerType {
  name: string;
  billing_id?: string;
  balance?: string;
  customer_id: string;
}

export interface CustomerTableItem extends CustomerType {
  subscriptions: string[];
  total_revenue_due: number;
}

export interface CustomerSummary {
  customers: CustomerTableItem[];
}
