import {
  Component,
  CreateComponent,
  CreateRecurringCharge,
  RecurringCharge,
} from "./plan-type";
import { FeatureType } from "./feature-type";
import { CurrencyType } from "./pricing-unit-type";

const InvoiceWhenOptions = ["invoice_on_attach", "invoice_on_subscription_end"];
export type InvoiceWhen = (typeof InvoiceWhenOptions)[number];

const AddOnBillingFrequencyOptions = ["one_time", "recurring"];
export type AddOnBillingFrequency =
  (typeof AddOnBillingFrequencyOptions)[number];

const AddOnTypeOptions: ["flat_fee", "usage"] = ["flat_fee", "usage"];
export type AddOnTypeOption = (typeof AddOnTypeOptions)[number];

export interface AddOnType {
  addon;
  addon_name: string | null;
  addon_id: string | null;
  description: string | null;
  flat_rate: number;
  recurring_charges: RecurringCharge[];
  components: Component[];
  features: FeatureType[];
  currency?: CurrencyType;
  active_instances: number;
  invoice_when: InvoiceWhen | null;
  billing_frequency: AddOnBillingFrequency | null;
  addon_type: AddOnTypeOption;
}

export interface AddOnSubscriptionType {
  end_date: Date;
  start_date: Date;
  fully_billed: boolean;
  addon: {
    addon_id: string;
    addon_name: string;
    addon_type: AddOnTypeOption;
    billing_frequency: AddOnBillingFrequency;
  };
}

export interface CreateAddOnType
  extends Omit<
    AddOnType,
    | "addon_id"
    | "recurring_charges"
    | "components"
    | "features"
    | "currency"
    | "active_instances"
    | "flat_rate"
  > {
  recurring_charges: CreateRecurringCharge[];
  components: CreateComponent[];
  features: string[];
  currency_code?: string;
}
export interface CreateAddOnFeatureBody {
  feature_id: string;
  version_ids?: string[];
  all_versions: boolean;
}
