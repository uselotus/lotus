export const TimePeriods = [
  "milliseconds",
  "seconds",
  "minutes",
  "hours",
  "days",
  "months",
  "quarters",
  "years",
  "total",
] as const;
export type TimePeriodType = (typeof TimePeriods)[number];

const MetricCategories = ["counter", "gauge", "rate", "custom"] as const;
export type MetricCategory = (typeof MetricCategories)[number];

const EventTypes = ["delta", "total"] as const;
export type EventType = (typeof EventTypes)[number];

export interface MetricType {
  metric_id: string;
  event_name: string;
  property_name?: string;
  usage_aggregation_type: string;
  billable_aggregation_type: string;
  granularity?: TimePeriodType;
  event_type?: EventType;
  metric_type: MetricCategory;
  metric_name: string;
  numeric_filters: NumericFilterType[];
  categorical_filters: CategoricalFilterType[];
  is_cost_metric: boolean;
  proration?: TimePeriodType;
  custom_sql?: string;
}

export interface CreateMetricType
  extends Omit<
    MetricType,
    | "metric_id"
    | "usage_aggregation_type"
    | "billable_aggregation_type"
    | "event_name"
  > {
  usage_aggregation_type?: string;
  billable_aggregation_type?: string;
  event_name?: string;
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

export interface CategoricalFilterType {
  property_name: string;
  operator: string;
  comparison_value: string[];
}

export interface NumericFilterType {
  property_name: string;
  operator: string;
  comparison_value: number;
}
