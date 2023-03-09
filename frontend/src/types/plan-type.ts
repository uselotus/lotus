import { MetricType } from "./metric-type";
import { FeatureType } from "./feature-type";
import { CurrencyType } from "./pricing-unit-type";
import { LightweightCustomerType } from "./customer-type";
import { AlertType } from "./alert-type";

export interface RecurringCharge {
  name: string;
  charge_timing: "in_advance" | "in_arrears";
  charge_behavior: "prorate" | "full";
  amount: number;
  pricing_unit: CurrencyType;
}

//create enum of day week month year null

export interface Tier {
  type: "flat" | "free" | "per_unit";
  cost_per_batch?: number;
  metric_units_per_batch?: number;
  batch_rounding_type?:
    | "round_up"
    | "round_down"
    | "round_nearest"
    | "no_rounding";
  range_start: number;
  range_end?: number;
}
export interface PriceAdjustment {
  price_adjustment_type: "percentage" | "fixed" | "fixed_override";
  price_adjustment_amount: number;
}
export interface CreateRecurringCharge {
  name: string;
  charge_timing: "in_advance" | "in_arrears";
  charge_behavior: "prorate" | "full";
  amount: number;
  pricing_unit_code?: string;
}

export interface PrepaidType {
  units: number | null;
  charge_behavior: "prorate" | "full";
}

export interface Component {
  billable_metric: MetricType;
  tiers: Tier[];
  id?: number;
  pricing_unit: CurrencyType;
  reset_interval_unit: "day" | "week" | "month" | "year" | null;
  reset_interval_count: number;
  invoicing_interval_unit: "day" | "week" | "month" | "year" | null;
  invoicing_interval_count: number;
  prepaid_charge?: number;
}
export interface CreateComponent
  extends Omit<Component, "billable_metric" | "pricing_unit"> {
  metric_id: string;
}
export interface CreatePlanVersionType {
  description?: string;
  plan_id?: string;
  features: string[];
  components: CreateComponent[];
  recurring_charges: CreateRecurringCharge[];
  usage_billing_frequency?: string;
  transition_to_plan_id: string;
  price_adjustment?: PriceAdjustment;
  make_active?: boolean;
  make_active_type?: string;
  day_anchor?: number;
  month_anchor?: number;
  currency_code?: string;
  version: number;
}
export interface CreateInitialVersionType extends CreatePlanVersionType {
  description?: string;
}
export interface InitialExternalLinks {
  source: string;
  external_plan_id: string;
}
export interface PlanVersionType
  extends Omit<
    CreatePlanVersionType,
    "components" | "currency_code" | "features" | "recurring_charges"
  > {
  description: string;
  plan_id: string;
  flat_fee_billing_type: string;
  flat_rate: number;
  status: string;
  components: Component[];
  recurring_charges: RecurringCharge[];
  version: number;
  version_id: string;
  created_by: string;
  created_on: string;
  transition_to: string;
  active_subscriptions: number;
  features: FeatureType[];
  plan_name?: string;
  usage_billing_frequency?: "monthly" | "quarterly" | "yearly";
  currency: CurrencyType;
  alerts: AlertType[];
}
export interface PlanType {
  plan_name: string;
  plan_duration: "monthly" | "quarterly" | "yearly";
  status: "active" | "archived" | "experimental";
  external_links: InitialExternalLinks[];
  plan_id: string;
  parent_plan: {
    plan_name: string;
    plan_id: string;
  } | null;
  target_customer: LightweightCustomerType | null;
  display_version: PlanVersionType;
  num_versions: number;
  active_subscriptions: number;
  tags: { tag_color: string; tag_hex: string; tag_name: string }[];
}

export interface PlanDetailType extends PlanType {
  versions: PlanVersionType[];
}

export interface CreatePlanExternalLinkType extends InitialExternalLinks {
  plan_id: string;
}

export interface LightweightPlanVersionType {
  plan_id: string;
  plan_name: string;
  version: number;
}

export interface PlansByCustomerArray {
  results: { plan_name: string; num_customers: number; percent_total: number };
  status?: string;
}

export interface CreatePlanType {
  plan_name: string;
  plan_duration: string;
  product_id?: string;
  plan_id?: string;
  status?: "active" | "archived" | "experimental";
  initial_version: CreateInitialVersionType;
  parent_plan_id?: string;
  target_customer_id?: string;
  initial_external_links?: InitialExternalLinks[];
}

export interface CreateVersionType {
  description: string;
  flat_fee_billing_type: string;
  plan_id: number;
  flat_rate: number;
  components: CreateComponent[];
  features: FeatureType[];
  usage_billing_frequency?: string;
  replace_plan_version_id?: string;
  make_active: boolean;
  make_active_type?: string;
  replace_immediately_type?: string;
  day_archor?: number;
  month_anchor?: number;
}

export interface PlanDisplay {
  name: string;
  color: string;
}

// UPDATE PLAN VERSIONS
export interface PlanVersionUpdateType {
  description?: string;
  status?: "active" | "archived";
  make_active_type?:
    | "replace_immediately"
    | "replace_on_active_version_renewal"
    | "grandfather_active";
  replace_immediately_type?:
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill"
    | "change_subscription_plan";
  transition_to_plan_id: string;
}
// update description
export interface PlanVersionUpdateDescriptionType
  extends PlanVersionUpdateType {
  description: string;
}
export interface PlanFeaturesAdd {
  feature_id: string;
  version_ids?: string[];
  all_versions?: boolean;
}
// archive plan
export interface ArchivePlanVersionType extends PlanVersionUpdateType {
  status: "archived";
}
export interface PlanVersionsType {
  success: boolean;
  message: string;
}

export interface PlanVersionFeatureAddBody {
  feature_id: string;
}
export interface PlanVersionReplacementMakeBody {
  version_to_replace: string[];
}
export interface PlanVersionReplacementSetBody {
  replace_with: string;
}
export interface PlanVersionAddTargetCustomerBody {
  customer_ids: string[] | null[];
}

// if we specify make_active_type as replace_immediately, must have a corresponding replace_immediately_type
export interface ReplaceImmediatelyType extends PlanVersionUpdateType {
  status: "active";
  make_active_type: "replace_immediately";
  replace_immediately_type:
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill"
    | "change_subscription_plan";
}

// if we have repalce on renewal or grandfather active as the make active type, then omit the replace immediately type
export interface ReplaceLaterType extends PlanVersionUpdateType {
  status: "active";
  make_active_type: "replace_on_active_version_renewal" | "grandfather_active";
}

// UPDATE PLANS
export interface UpdatePlanType {
  plan_name?: string;
  plan_description: string | null;
  taxjar_code: string | null;
  active_from: string;
  active_to: string | null;
}
export interface CreateTagsPlanBody {
  tags: PlanType["tags"];
}
export interface CreateTagsType extends PlanVersionsType {
  tags: PlanType["tags"];
}
