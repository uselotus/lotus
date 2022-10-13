import { CreatePlanType } from "./plan-type";

export interface BacktestType {
  backtest_name: string;
  backtest_id: string;
  status: string;
  start_time: string;
  end_time: string;
  time_created: string;
  kpis: string[];
}

export interface CreateBacktestType {
  backtest_name: string;
  start_time: string;
  end_time: string;
  kpis: string[];
  substitutions: Substitution[];
}

export interface Substitution {
  new_plan: CreatePlanType;
  old_plan: string[];
}
