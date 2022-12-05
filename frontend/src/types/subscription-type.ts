import { CustomerType } from "./customer-type";
import { PlanVersionType } from "./plan-type";
export interface SubscriptionTotals {
  period_1_total_subscriptions: number;
  period_2_total_subscriptions: number;
  period_1_new_subscriptions: number;
  period_2_new_subscriptions: number;
}

export interface SubscriptionType {
  customer: CustomerType[];
  billing_plan: PlanVersionType;
  start_date: string;
  end_date?: string;
  status?: "active" | "ended" | "not_started";
  auto_renew?: boolean;
  is_new?: boolean;
  subscription_id?: string;
  subscription_filters?: {
    value: string;
    property_name: string;
  }[];
}

export interface CreateSubscriptionType
  extends Omit<SubscriptionType, "customer" | "billing_plan"> {
  customer_id: string;
  plan_id: string;
}

export interface UpdateSubscriptionType {
  replace_plan_id?: string;
  end_date?: string;
  turn_off_auto_renew?: boolean;
  replace_plan_invocing_behavior?: string;
}

export interface CancelSubscriptionType {
  bill_usage: boolean;
  flat_fee_behavior: "refund" | "prorate" | "charge_full";
  invoicing_behavior_on_cancel: "add_to_next_invoice" | "bill_now";
}

export interface ChangeSubscriptionPlanType extends UpdateSubscriptionType {
  replace_plan_id: string;
}

export interface TurnSubscriptionAutoRenewOffType
  extends UpdateSubscriptionType {
  turn_off_auto_renew: true;
}
