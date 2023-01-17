import { MetricType } from "./metric-type";

export interface CreateAlertType {
  metric_id: string;
  plan_version_id: string;
  threshold: number;
}

export interface AlertType {
  usage_alert_id: string;
  threshold: number;
  plan_version: {
    plan_version_id: string;
    plan_name: string;
    version: number;
  };
  metric: MetricType;
}
