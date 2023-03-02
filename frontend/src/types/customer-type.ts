import { PlanDisplay, PlanVersionType } from "./plan-type";
import { SubscriptionType } from "./subscription-type";
import { InvoiceType } from "./invoice-type";
import { CurrencyType } from "./pricing-unit-type";
import { PaymentProcessorType } from "./payment-processor-type";
import { AddressType, TaxProviderType } from "./account-type";

export interface CustomerType {
  customer_id: string;
  shipping_address?: AddressType;
  billing_address?: AddressType;
  tax_providers: TaxProviderType[];
  email: string;
  customer_name: string;
  invoices: InvoiceType[];
  total_amount_due: number;
  subscriptions: SubscriptionType[];
  integrations: object;
  default_currency: CurrencyType;
  has_payment_method: boolean;
  payment_provider?: PaymentProcessorType;
  payment_provider_id?: string;
  tax_rate?: number;
  timezone: string;
}

export type LightweightCustomerType = Omit<
  CustomerType,
  | "invoices"
  | "subscriptions"
  | "default_currency"
  | "total_amount_due"
  | "integrations"
>;

export interface CustomerCreateType
  extends Omit<
    CustomerType,
    | "invoices"
    | "subscriptions"
    | "default_currency"
    | "customer_name"
    | "payment_provider"
    | "total_amount_due"
    | "integrations"
    | "has_payment_method"
  > {
  customer_name?: string;
  payment_provider?: string;
  payment_provider_id?: string;
  properties?: { [key: string]: string };
  default_currency_code?: string;
}

export interface CustomerUpdateType {
  default_currency_code?: string;
  shipping_address?: CustomerType["shipping_address"];
  billing_address?: CustomerType["billing_address"];
  tax_rate?: number;
  timezone?: string;
}

export interface CustomerTableItem extends CustomerSummary {
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
