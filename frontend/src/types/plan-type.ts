import { MetricType } from "./metric-type";
import { FeatureType } from "./feature-type";
export interface PlanType {
  name: string;
  components: Component[];
  interval: string;
  description: string;
  flat_rate: number;
  currency: string;
  id: number;
  pay_in_advance: boolean;
  time_created: string;
  billing_plan_id: string;
  active_subscriptions: number;
  features: FeatureType[];
}

export interface PlansByCustomerArray {
  results: { plan_name: string; num_customers: number; percent_total: number };
  status?: string;
}

export interface UpdatePlanType {
  old_billing_plan_id: string;
  updated_billing_plan: CreatePlanType;
  update_behavior: string;
}
export interface CreatePlanType {
  name: string;
  components: CreateComponent[];
  interval: string;
  description: string;
  flat_rate: number;
  pay_in_advance: boolean;
  currency?: string;
  features: FeatureType[];
  status?: string;
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
  id: number;
}
export interface PlanDisplay {
  name: string;
  color: string;
}
