export interface CreateBalanceAdjustmentType {
    customer_id: string;
    amount: number;
    amount_currency: string;
    description: string;
    pricing_unit_code: string;
}
