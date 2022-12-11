export interface APIKeyType {
  name: string;
  prefix: string;
  expiry_date: string;
  created: string;
}

export interface APIKeyCreate {
  name: string;
  expiry_date?: string;
}

export interface APIKeyCreateResponse {
  api_key: APIKeyType;
  key: string;
}
