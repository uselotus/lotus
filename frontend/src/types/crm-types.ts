// Export an interface that mirrors the SingleCRMProviderSerializer class
const CRMProviders = ["salesforce"] as const;
export type CRMProviderType = (typeof CRMProviders)[number];

export interface CRMConnectionStatus {
  crm_provider_name: CRMProviderType;
  connected: boolean;
  self_hosted: boolean;
  working: boolean;
  connection_id: string | undefined;
  account_id: string | undefined;
  native_org_url: string | undefined;
}

export interface CRMSettingsParams {
  setting_group: "crm";
  setting_name?: string;
}

export interface CRMSetting {
  setting_group: "crm";
  setting_id: string;
  setting_name: string;
  setting_values: any;
}
