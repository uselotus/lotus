import { LightweightCustomerType } from "./customer-type";
import { PricingUnit } from "./pricing-unit-type";

export interface CreateBalanceAdjustmentType {
  customer_id: string;
  amount: number;
  amount_currency: string;
  description: string;
  pricing_unit_code: string;
  effective_at: string;
  expires_at?: string;
  amount_paid?: number;
  amount_paid_currency?: string;
}

export interface BalanceAdjustmentType {
  amount: number;
  amount_currency: string;
  description: string;
  created: string;
  effective_at: string;
  expires_at: string;
  adjustment_id: string;
  parent_adjustment_id: string;
  pricing_unit: PricingUnit;
  customer: LightweightCustomerType;
  status: "active" | "inactive";
}
