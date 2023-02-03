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

const AddonBillingFrequencyOptions = ["one_time", "recurring"];
export type AddonBillingFrequency =
  (typeof AddonBillingFrequencyOptions)[number];

const AddonTypeOptions: ["flat_fee", "usage"] = ["flat_fee", "usage"];
export type AddonTypeOption = (typeof AddonTypeOptions)[number];

export interface AddonType {
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
  billing_frequency: AddonBillingFrequency | null;
  addon_type: AddonTypeOption;
}

export interface CreateAddonType
  extends Omit<
    AddonType,
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
