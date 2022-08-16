export interface PlanType {
  name: string;
  components: Component[];
  billing_interval: string;
  description: string;
  flat_rate: number;
}

interface Component {
  metric_name: string;
  property_name: string;
  free_metric_quantity: number;
  cost_per_metric: number;
  aggregation_type: string;
  unit_per_cost: number;
}
