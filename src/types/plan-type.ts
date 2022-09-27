import { MetricType } from "./metric-type";
export interface PlanType {
  name: string;
  components: Component[];
  interval: string;
  description: string;
  flat_rate: number;
  currency: string;
  id: number;
  time_created: string;
  billing_plan_id: string;
}

export interface CreatePlanType {
  name: string;
  components: CreateComponent[];
  interval: string;
  description: string;
  flat_rate: number;
  pay_in_advance: boolean;
  currency?: string;
}

export interface CreateComponent {
  billable_metric?: number;
  free_metric_quantity: number;
  cost_per_batch: number;
  metric_units_per_batch: number;
}

export interface Component {
  billable_metric: MetricType;
  free_metric_quantity: string;
  cost_per_batch: string;
  metric_units_per_batch: string;
  id: number;
}
export interface PlanDisplay {
  name: string;
  color: string;
}
