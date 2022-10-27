export interface PaymentProcessorStatusType {
  payment_provider_name: string;
  connected: boolean;
  redirect_link: string;
}

export interface PaymentProcessorConnectionResponseType {
  payment_processor: string;
  success: boolean;
  details: string;
}

export interface PaymentProcessorConnectionRequestType {
  payment_processor: string;
  data: StripeConnectionRequestType;
}

export interface StripeConnectionRequestType {
  authorization_code: string;
}
