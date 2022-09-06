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
  cost_per_metric: number;
  metric_amount_per_cost: number;
}

export interface Component {
  billable_metric: MetricType;
  free_metric_quantity: string;
  cost_per_metric: string;
  metric_amount_per_cost: string;
  id: number;
}
export interface PlanDisplay {
  name: string;
  color: string;
}
