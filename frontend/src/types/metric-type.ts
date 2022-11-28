export interface MetricType {
  event_name: string;
  property_name: string;
  usage_aggregation_type: string;
  billable_aggregation_type?: string;
  id?: number;
  billable_metric_name?: string;
  metric_type: "counter" | "stateful" | "rate";
  numeric_filters?: NumericFilterType[];
  categorical_filters?: CateogricalFilterType[];
  granularity?: string;
  event_type?: "delta" | "total";
  is_cost_metric?: boolean;
  properties?: string[];
}

export interface MetricNameType {
  event_name: string;
  property_name: string;
  aggregation_type: string;
  id: number;
  billable_metric_name: string;
}

export interface MetricUsage {
  metrics: { [key: string]: MetricUsageValue };
}
interface MetricUsageValue {
  data: UsageData[];
  top_n_customers?: { name: string }[];
  total_usage: number;
  top_n_customers_usage?: number;
}

interface UsageData {
  date: string;
  customer_usages: CustomerUsage[];
}

interface CustomerUsage {
  metric_amount: number;
  customer: { name: string };
}

export interface CateogricalFilterType {
  property_name: string;
  operator: string;
  comparison_value: string[];
}

export interface NumericFilterType {
  property_name: string;
  operator: string;
  comparison_value: number;
}
