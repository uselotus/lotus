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
}

export interface CreateSubscriptionType
  extends Omit<SubscriptionType, "customer" | "billing_plan"> {
  customer_id: string;
  plan_id: string;
}

export interface UpdateSubscriptionType {
  plan_id?: string;
  status?: "ended";
  auto_renew?: boolean;
  replace_immediately_type?:
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill"
    | "change_subscription_plan";
}

export interface CancelSubscriptionType
  extends Omit<UpdateSubscriptionType, "plan_id"> {
  status: "ended";
  replace_immediately_type:
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill";
}

export interface ChangeSubscriptionPlanType
  extends Omit<UpdateSubscriptionType, "status"> {
  plan_id: string;
  replace_immediately_type:
    | "change_subscription_plan"
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill";
}

export interface TurnSubscriptionAutoRenewOffType
  extends Omit<UpdateSubscriptionType, "plan_id" | "status"> {
  auto_renew: false;
}
