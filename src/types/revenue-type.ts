import { MetricType } from "./metric-type";
export interface RevenueType {
  revenue_period_1: RevenuePeriod;
  revenue_period_2: RevenuePeriod;
}

interface RevenuePeriod {
  total_revenue: number;
  data: RevenueData[];
  metric: MetricType;
}

interface RevenueData {
  day: string;
  metric_revenue: number;
}
