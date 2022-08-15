export interface StripeConnectType {
  code: string;
  scope: string;
  client_id: string;
}

export interface StripeStatusType {
  connected: boolean;
}

export interface StripeOauthType {
  authorization_code: string;
}
