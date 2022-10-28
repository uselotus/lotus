import { MetricType } from "./metric-type";
import { FeatureType } from "./feature-type";

export interface PlanType {
  plan_name: string;
  plan_duration: string;
  interval: string;
  description: string;
  flat_rate: number;
  id: number;
  time_created: string;
  version_id: string;
  active_subscriptions: number;
  num_versions: number;
  versions?: PlanVersionType[];
  display_version?: PlanVersionType;
  parent_plan?: {
    plan_name: string;
    plan_id: string;
  };
  target_customers?: { name: string; customer_id: string };
}

interface PlanVersionType {
  description?: string;
  plan_id?: string;
  features: FeatureType[];
  components: Component[];
  flat_rate: number;
  usage_billing_type: string;
  flat_fee_billing_type: string;
}

export interface PlanVersionDisplayType extends PlanVersionType {
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
  usage_billing_type: string;
}

export interface PlansByCustomerArray {
  results: { plan_name: string; num_customers: number; percent_total: number };
  status?: string;
}

export interface UpdatePlanType {
  old_version_id: string;
  updated_billing_plan: CreatePlanType;
  update_behavior: string;
}

export interface CreatePlanType {
  plan_name: string;
  plan_duration: string;
  initial_version: CreateInitialVersionType;
  plan_id?: string;
  product_id?: string;
  currency?: string;
  status?: string;
  parent_plan_id?: string;
  target_customer_id?: string;
}

export interface CreateVersionType {
  description: string;
  flat_fee_billing_type: string;
  plan_id: number;
  flat_rate: number;
  components: Component[];
  features: FeatureType[];
  usage_billing_type: string;
  replace_plan_version_id?: string;
  make_active: boolean;
  make_active_type?: string;
  replace_immediately_type?: string;
}

export interface CreateComponent {
  billable_metric_name?: string;
  free_metric_units: number;
  cost_per_batch: number;
  metric_units_per_batch: number;
  max_metric_units: number;
}

export interface Component {
  billable_metric: MetricType;
  free_metric_units: string;
  cost_per_batch: string;
  metric_units_per_batch: string;
  max_metric_units: string;
  id?: number;
}
export interface PlanDisplay {
  name: string;
  color: string;
}

export interface CreateInitialVersionType
  extends Omit<PlanVersionType, "components"> {
  components: CreateComponent[];
}
