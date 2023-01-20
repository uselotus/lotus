import { LightweightCustomerType } from "./customer-type";
import { CurrencyType } from "./pricing-unit-type";

export interface CreateCreditType {
  customer_id: string;
  amount: number;
  description?: string;
  currency_code: string;
  effective_at?: string;
  expires_at?: string;
  amount_paid?: number;
  amount_paid_currency_code?: string;
}

export interface DrawdownType {
  credit_id: string;
  amount: number;
  applied_at: string;
  description: string;
}

export interface CreditType {
  amount: number;
  amount_paid_currency: CurrencyType;
  amount_paid: number;
  amount_remaining: number;
  description: string;
  effective_at: string;
  expires_at: string;
  credit_id: string;
  currency: CurrencyType;
  customer: LightweightCustomerType;
  status: "active" | "inactive";
  drawdowns: DrawdownType[];
}
