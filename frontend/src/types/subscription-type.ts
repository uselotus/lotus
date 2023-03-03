import { AddOnSubscriptionType, AddOnType } from "./addon-type";
import { LightweightCustomerType } from "./customer-type";
import { LightweightPlanVersionType } from "./plan-type";

export interface SubscriptionTotals {
  period_1_total_subscriptions: number;
  period_2_total_subscriptions: number;
  period_1_new_subscriptions: number;
  period_2_new_subscriptions: number;
}

export interface SubscriptionType {
  subscription_id: string;
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  addons: AddOnSubscriptionType[];
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
  end_date?: string;
  turn_off_auto_renew?: boolean;
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
export interface SwitchPlanSubscriptionBody {
  new_version_id: string;
  invoicing_behavior: string;
  usage_behavior: string;
}

export interface ChangeSubscriptionPlanType extends UpdateSubscriptionType {
  replace_plan_id: string;
}

export interface TurnSubscriptionAutoRenewOffType
  extends UpdateSubscriptionType {
  turn_off_auto_renew: true;
}

export interface CreateSubscriptionAddOnBody {
  attach_to_customer_id: string;
  attach_to_plan_id: string;
  attach_to_subscription_filters?: SubscriptionType["subscription_filters"];
  addon_id: string;
  quantity?: number;
}
export interface CancelCreateSubscriptionAddOnQueryParams {
  attached_to_customer_id: string;
  attached_to_plan_id: string;
  attached_to_subscription_filters?: SubscriptionType["subscription_filters"];
  addon_id: string;
  quantity?: number;
}
export interface CancelCreateSubscriptionAddOnBody {
  flat_fee_behavior: string;
  usage_behavior: string;
  invoicing_behavior: string;
}
export interface CreateSubscriptionAddOnType
  extends Omit<SubscriptionType, "start_date" | "end_date" | "customer"> {
  addon: AddOnType;
  fully_billed: boolean;
  parent: SubscriptionType;
}
