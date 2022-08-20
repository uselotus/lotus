import { PlanDisplay } from "./plan-type";
export interface CustomerType {
  name: string;
  billing_id?: string;
  balance?: string;
  customer_id: string;
}
export interface CustomerTableItem extends CustomerType {
  plan: PlanDisplay;
}
