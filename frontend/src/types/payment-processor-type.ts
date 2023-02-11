export interface PaymentProcessorStatusType {
  payment_provider_name: "stripe" | "braintree";
  connected: boolean;
  redirect_url: string;
  self_hosted: boolean;
  connection_id: string;
}

export interface PaymentProcessorConnectionResponseType {
  payment_processor: string;
  success: boolean;
  details: string;
}

export interface PaymentProcessorConnectionRequestType {
  payment_processor: "stripe" | "braintree";
  data: StripeConnectionRequestType | BraintreeConnectionRequestType;
}

export interface StripeConnectionRequestType {
  authorization_code: string;
}

export interface BraintreeConnectionRequestType {
  merchant_id: string;
  code: string;
}

export const integrationsMap = {
  stripe: {
    name: "Stripe",
    icon: "https://cdn.neverbounce.com/images/integrations/square/stripe-square.png",
    description:
      "Charge and invoice your customers through your Stripe account",
    connection_id_name: "Stripe Account ID",
  },
  braintree: {
    name: "Braintree",
    icon: "https://cdn.neverbounce.com/images/integrations/square/stripe-square.png",
    description:
      "Charge and invoice your customers through your Braintree account",
    connection_id_name: "Merchant ID",
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
