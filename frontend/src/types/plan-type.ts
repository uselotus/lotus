import { MetricType } from "./metric-type";
import { FeatureType } from "./feature-type";

export interface PlanType {
  plan_name: string;
  plan_duration: "monthly" | "quarterly" | "yearly";
  product_id?: string;
  plan_id: string;
  status: "active" | "archived" | "experimental";
  parent_plan?: {
    plan_name: string;
    plan_id: string;
  };
  target_customer?: {
    name: string;
    customer_id: string;
  };
  created_on: string;
  created_by: string;
  display_version?: PlanVersionType;
  num_versions: number;
  active_subscriptions: number;
  external_links?: InitialExternalLinks[];
}

export interface PlanDetailType extends Omit<PlanType, "display_version"> {
  versions: PlanVersionType[];
}

export interface CreatePlanVersionType {
  description?: string;
  plan_id?: string;
  features: FeatureType[];
  components: CreateComponent[];
  flat_rate: number;
  usage_billing_frequency?: string;
  flat_fee_billing_type: string;
  price_adjustment?: PriceAdjustment;
  make_active?: boolean;
  make_active_type?: string;
}

export interface CreatePlanExternalLinkType extends InitialExternalLinks {
    plan_id: string,
}

export interface PriceAdjustment {
  price_adjustment_type: "percentage" | "fixed" | "fixed_override";
  price_adjustment_amount: number;
}

export interface PlanVersionType
  extends Omit<CreatePlanVersionType, "components"> {
  description: string;
  plan_id: string;
  flat_fee_billing_type: string;
  flat_rate: number;
  status: string;
  components: Component[];
  version: number;
  version_id: string;
  created_by: string;
  created_on: string;
  active_subscriptions: number;
  features: FeatureType[];
  usage_billing_frequency?: "monthly" | "quarterly" | "yearly";
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

export interface InitialExternalLinks {
    source: string;
    external_plan_id: string;
}

export interface CreateInitialVersionType extends CreatePlanVersionType {
  description?: string;
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
}

export interface CreateComponent
  extends Omit<Component, "id" | "billable_metric"> {
  billable_metric_name: string;
}

export interface Component {
  billable_metric: MetricType;
  free_metric_units: number;
  cost_per_batch: number;
  metric_units_per_batch: number;
  max_metric_units: number;
  id?: number;
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
}
// update description
export interface PlanVersionUpdateDescriptionType
  extends PlanVersionUpdateType {
  description: string;
}

// archive plan
export interface ArchivePlanVersionType extends PlanVersionUpdateType {
  status: "archived";
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
  status?: "active" | "archived";
}
