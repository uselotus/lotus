export interface PaymentProcessorStatusType {
  payment_provider_name: string;
  connected: boolean;
  redirect_url: string;
}

export interface PaymentProcessorConnectionResponseType {
  payment_processor: string;
  success: boolean;
  details: string;
}
export interface StripeConnectionRequestType {
  authorization_code: string;
}
export interface PaymentProcessorConnectionRequestType {
  payment_processor: string;
  data: StripeConnectionRequestType | object;
}

export const integrationsMap = {
  stripe: {
    name: "Stripe",
    icon: "https://cdn.neverbounce.com/images/integrations/square/stripe-square.png",
    description:
      "Charge and invoice your customers through your Stripe account",
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
