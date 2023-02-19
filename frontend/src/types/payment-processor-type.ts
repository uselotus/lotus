const PaymentProcessors = ["stripe", "braintree"] as const;
export type PaymentProcessorType = (typeof PaymentProcessors)[number];

export interface PaymentProcessorStatusType {
  payment_provider_name: PaymentProcessorType;
  connected: boolean;
  redirect_url: string;
  self_hosted: boolean;
  connection_id: string;
  working: boolean;
  account_id: string;
}

export interface PaymentProcessorConnectionResponseType {
  payment_processor: string;
  success: boolean;
  details: string;
}

export interface PaymentProcessorConnectionRequestType {
  payment_processor: PaymentProcessorType;
  data: StripeConnectionRequestType | BraintreeConnectionRequestType;
}

export interface StripeConnectionRequestType {
  authorization_code: string;
}

export interface BraintreeConnectionRequestType {
  merchant_id?: string;
  nango_connnected: boolean;
}

export interface PaymentProcessorImportCustomerResponse {
  status: string;
  detail: string;
}

export interface Source {
  source: PaymentProcessorType;
}

export interface TransferSub extends Source {
  end_now: boolean;
}

export interface PaymentProcessorSettingsParams {
  setting_group: PaymentProcessorType;
  setting_name?: string;
}

export interface PaymentProcessorSetting {
  setting_group: PaymentProcessorType;
  setting_id: string;
  setting_name: string;
  setting_values: any;
}

export interface UpdatePaymentProcessorSettingParams {
  setting_id: string;
  setting_values: boolean;
}

export const integrationsMap = {
  stripe: {
    name: "Stripe",
    icon: "https://cdn.neverbounce.com/images/integrations/square/stripe-square.png",
    description:
      "Charge and invoice your customers through your Stripe account",
    account_id_name: "Account ID",
  },
  braintree: {
    name: "Braintree",
    icon: "https://pbs.twimg.com/profile_images/1146433479091118081/Yn29TbtJ_400x400.png",
    description:
      "Charge and invoice your customers through your Braintree account",
    account_id_name: "Merchant ID",
  },
  snowflake: {
    name: "Snowflake",
    icon: "https://i.imgur.com/iNCQmMu.png",
    description: "Sync data to your Snowflake warehouse",
  },
  salesforce: {
    name: "Salesforce",
    icon: "https://cdn-icons-png.flaticon.com/512/5968/5968914.png",
    description: "Sync data to your Salesforce account",
  },
};
