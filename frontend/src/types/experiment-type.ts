import { PlanType } from "./plan-type";

export interface BacktestType {
  backtest_name: string;
  backtest_id: string;
  status: string;
  start_date: string;
  end_date: string;
  time_created: string;
  kpis: string[];
}

export interface RevenuByMetricResults {
  metric_name: string;
  original_plan_revenue: number;
  new_plan_revenue: number;
}

interface TopCustomerResults {
  customer_id: string;
  customer_name: string;
  value: number;
}
export interface RevenueChartResults {
  date: string;
  original_plan_revenue: number;
  new_plan_revenue: number;
}
interface SubstitutionResults {
  new_plan: PlanType;
  original_plan: PlanType;
}
export interface Substitution {
  new_plan: string;
  original_plans: string[];
  new_plan_name: string;
  original_plan_names: string[];
}
export interface CreateBacktestType {
  backtest_name: string;
  start_date: string;
  end_date: string;
  kpis: string[];
  substitutions: Substitution[];
}

export interface SpecificResults {
  substitution_name: string;
  pct_revenue_change: number;
  new_plan: { plan_name: string; plan_id: string; plan_revenue: number };
  original_plan: { plan_name: string; plan_id: string; plan_revenue: number };
  results: {
    cumulative_revenue: RevenueChartResults[];
    revenue_by_metric: RevenuByMetricResults[];
    top_customers: {
      original_plan_revenue: TopCustomerResults[];
      new_plan_revenue: TopCustomerResults[];
      biggest_pct_increase: TopCustomerResults[];
      biggest_pct_decrease: TopCustomerResults[];
    };
  };
}
interface ResultsOverview {
  new_plans_revenue: number;
  original_plans_revenue: number;
  pct_revenue_change: number;
  substitution_results: SpecificResults[];
}
export interface BacktestResultType extends BacktestType {
  backtest_subsitutions: SubstitutionResults[];
  backtest_results: ResultsOverview;
}
