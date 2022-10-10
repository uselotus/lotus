import { MetricType } from "./metric-type";
export interface SubscriptionTotals {
  period_1_total_subscriptions: number;
  period_2_total_subscriptions: number;
  period_1_new_subscriptions: number;
  period_2_new_subscriptions: number;
}

export interface CreateSubscriptionType {
  customer_id: string;
  billing_plan_id: string;
  start_date?: string;
}

export interface SubscriptionType {
  components: ComponentType[];
  billing_plan: PlanSimple;
  usage_revenue_due: number;
  flat_revenue_due: number;
  total_revenue_due: number;
}

export interface UpdateSubscriptionType {
  subscription_id: string;
  new_billing_plan_id: string;
  update_behavior: string;
}

interface ComponentType {
  units_usage: number;
  usage_revenue: number;
  plan_component: PlanComponent;
}
interface PlanComponent {
  billable_metric: MetricType;
  id: number;
  free_metric_units: number;
  cost_per_batch: number;
  metric_units_per_batch: number;
}
interface PlanSimple {
  url: string;
  name: string;
  id: number;
}
