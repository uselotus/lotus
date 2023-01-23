export interface MetricType {
  event_name: string;
  property_name: string;
  usage_aggregation_type: string;
  billable_aggregation_type?: string;
  metric_id: string;
  metric_name?: string;
  numeric_filters?: NumericFilterType[];
  categorical_filters?: CateogricalFilterType[];
  granularity?:
    | "seconds"
    | "minutes"
    | "hours"
    | "days"
    | "months"
    | "quarters"
    | "years"
    | "total";
  proration?:
    | "seconds"
    | "minutes"
    | "hours"
    | "days"
    | "months"
    | "quarters"
    | "years"
    | "total";
  event_type?: "delta" | "total";
  is_cost_metric?: boolean;
  properties?: string[];
  metric_type: "counter" | "gauge" | "rate" | "custom";
  custom_sql?: string;
}

export interface MetricUsage {
  metrics: { [key: string]: MetricUsageValue };
}
interface MetricUsageValue {
  data: UsageData[];
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
