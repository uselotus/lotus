import { LightweightCustomerType } from "./customer-type";
import { LightweightPlanVersionType } from "./plan-type";

export interface SubscriptionTotals {
  period_1_total_subscriptions: number;
  period_2_total_subscriptions: number;
  period_1_new_subscriptions: number;
  period_2_new_subscriptions: number;
}

export interface SubscriptionType {
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  is_new: boolean;
  subscription_filters: {
    value: string;
    property_name: string;
  }[];
  customer: LightweightCustomerType;
  billing_plan: LightweightPlanVersionType;
}

export interface CreateSubscriptionType
  extends Omit<SubscriptionType, "customer" | "billing_plan" | "end_date"> {
  customer_id: string;
  plan_id: string;
  end_date?: string;
}

export interface UpdateSubscriptionType {
  replace_plan_id?: string;
  end_date?: string;
  turn_off_auto_renew?: boolean;
  invocing_behavior?: string;
}

export interface CancelSubscriptionQueryParams {
  customer_id: string;
  plan_id?: string;
  subscription_filters?: {
    value: string;
    property_name: string;
  }[];
}

export interface CancelSubscriptionBody {
  usage_behavior: "bill_full" | "bill_none";
  flat_fee_behavior: "refund" | "charge_prorated" | "charge_full";
  invoicing_behavior: "add_to_next_invoice" | "invoice_now";
}

export interface ChangeSubscriptionPlanType extends UpdateSubscriptionType {
  replace_plan_id: string;
}

export interface TurnSubscriptionAutoRenewOffType
  extends UpdateSubscriptionType {
  turn_off_auto_renew: true;
}
