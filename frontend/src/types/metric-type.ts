export interface MetricType {
  event_name: string;
  property_name: string;
  aggregation_type: string;
  id?: number;
  billable_metric_name?: string;
  metric_type: string;
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
