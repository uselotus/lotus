export interface StripeImportCustomerResponse {
  status: string;
  detail: string;
}

export interface Source {
  source: string;
}

export interface TransferSub extends Source {
  end_now: boolean;
}

export interface StripeSettingsParams {
  setting_group: "stripe";
  setting_name?: string;
}

export interface StripeSetting {
  setting_group: string;
  setting_id: string;
  setting_name: string;
  setting_values: {
    value: boolean;
  };
}

export interface UpdateStripeSettingParams {
  setting_id: string;
  setting_values: boolean;
}
