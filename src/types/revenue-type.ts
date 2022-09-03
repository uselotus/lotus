import { MetricType } from "./metric-type";
export interface RevenueType {
  daily_usage_revenue_period_1: RevenuePeriod[];
  daily_usage_revenue_period_2: RevenuePeriod[];
  total_revenue_period_1: number;
  total_revenue_period_2: number;
}

export interface RevenuePeriod {
  total_revenue: number;
  data: RevenueData[];
  metric: MetricType;
}

interface RevenueData {
  day: string;
  metric_revenue: number;
}
