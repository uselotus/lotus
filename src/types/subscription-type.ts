import { MetricType } from "./metric-type";
export interface SubscriptionTotals {
  period_1_total_subscriptions: number;
  period_2_total_subscriptions: number;
  period_1_new_subscriptions: number;
  period_2_new_subscriptions: number;
}

export interface SubscriptionType {
  components: ComponentType[];
  billing_plan: PlanSimple;
  usage_revenue_due: number;
  flat_revenue_due: number;
  total_revenue_due: number;
}

interface ComponentType {
  units_usage: number;
  usage_revenue: number;
  plan_component: PlanComponent;
}
interface PlanComponent {
  billable_metric: MetricType;
  id: number;
  free_metric_quantity: number;
  cost_per_metric: number;
  metric_amount_per_cost: number;
}
interface PlanSimple {
  url: string;
  name: string;
  id: number;
}
