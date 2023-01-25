import { Component, CreateComponent } from "./plan-type";
import { FeatureType } from "./feature-type";
import { CurrencyType } from "./pricing-unit-type";

const InvoiceWhenOptions = ["invoice_on_attach", "invoice_on_subscription_end"];
export type InvoiceWhen = (typeof InvoiceWhenOptions)[number];

const AddonBillingFrequencyOptions = ["one_time", "recurring"];
export type AddonBillingFrequency =
  (typeof AddonBillingFrequencyOptions)[number];

const RecurringFlatFeeTimingOptions = ["in_advance", "in_arrears"];
export type RecurringFlatFeeTiming =
  (typeof RecurringFlatFeeTimingOptions)[number];

const AddonTypeOptions: ["flat_fee", "usage"] = ["flat_fee", "usage"];
export type AddonTypeOption = (typeof AddonTypeOptions)[number];

export interface AddonType {
  addon_name: string | null;
  addon_id: string | null;
  description: string | null;
  flat_rate: number;
  components: Component[];
  features: FeatureType[];
  currency?: CurrencyType;
  active_instances: number;
  invoice_when: InvoiceWhen | null;
  billing_frequency: AddonBillingFrequency | null;
  recurring_flat_fee_timing?: RecurringFlatFeeTiming | null;
  addon_type: AddonTypeOption;
}

export interface CreateAddonType
  extends Omit<
    AddonType,
    | "addon_id"
    | "components"
    | "features"
    | "currency"
    | "active_instances"
    | "addon_type"
  > {
  components: CreateComponent[];
  features: string[];
  currency_code?: string;
  addon_type: AddonTypeOption;
}
