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
  metric: string;
}

interface RevenueData {
  date: string;
  metric_revenue: number;
}

export interface CustomerCostType {
  per_day: {
    date: string;
    cost_date: CostType[];
    revenue: number;
  };
  total_cost: number;
  total_revenue: number;
  margin: number;
}

export interface CostType {
  cost: number;
  metric: MetricType;
}
