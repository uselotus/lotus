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

export interface PaymentProcessorConnectionRequestType {
  payment_processor: string;
  data: StripeConnectionRequestType | object;
}

export interface StripeConnectionRequestType {
  authorization_code: string;
}

export const integrationsMap = {
  stripe: {
    name: "Stripe",
    icon: "https://cdn.neverbounce.com/images/integrations/square/stripe-square.png",
    description:
      "Charge and invoice your customers through your Stripe account",
  },
};
