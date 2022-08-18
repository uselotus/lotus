export interface StripeConnectType {
  code: string;
  scope: string;
  client_id: string;
}

export interface StripeStatusType {
  connected: boolean;
}

export interface StripeOauthType {
  details: string;
  success: boolean;
}
