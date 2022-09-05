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
