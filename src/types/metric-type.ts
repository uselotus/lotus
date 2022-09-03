export interface MetricType {
  event_name: string;
  property_type: string;
  aggregation_type: string;
  id: number;
}

export interface MetricUsage {
  [key: string]: MetricUsageValue;
}
interface MetricUsageValue {
  metric: MetricType;
  data: UsageData[];
  top_n_customers: { name: string }[];
  total_usage: number;
  top_n_customers_usage: number;
}

interface UsageData {
  date: string;
  customer_usages: CustomerUsage[];
}

interface CustomerUsage {
  metric_amount: number;
  customer: { name: string };
}
