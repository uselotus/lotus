import { PlanType } from "./plan-type";
import { CurrencyType } from "./pricing-unit-type";
import { PaymentProcessorType } from "./payment-processor-type";

export const TaxProviders = ["lotus", "taxjar"] as const;
export type TaxProviderType = (typeof TaxProviders)[number];

export interface AddressType {
  organization: number;
  city: string;
  country: string;
  line1: string;
  line2?: string | null;
  postal_code: string;
  state?: string | null;
}
export interface CreateOrgAccountType {
  username: string;
  password: string;
  email: string;
  organization_name: string;
  industry: string;
  invite_token?: string | null;
}

export interface UserType {
  username: string;
  email: string;
  role: string;
  status: string;
}

export interface OrganizationSettingsType {
  [key: string]: {
    setting_values: object[];
    setting_id: string;
    setting_group: string;
    setting_name: string;
  };
}

export interface UpdateOrganizationPPType {
  org_id: string;
  payment_provider: PaymentProcessorType;
  payment_provider_id: string;
  nango_connected?: boolean;
}

export interface OrganizationType {
  organization_name: string;
  payment_provider_ids: object;
  address?: AddressType;
  users: UserType[];
  default_currency: CurrencyType;
  available_currencies: CurrencyType[];
  organization_id: string;
  plan_tags: PlanType["tags"];
  tax_rate?: number;
  timezone: string;
  payment_grace_period: number;
  subscription_filter_keys: string[];
  current_user: { username: string };
  linked_organizations: {
    current: boolean;
    organization_id: string;
    organization_type: string;
    organization_name: string;
  }[];
  tax_providers: TaxProviderType[];
  crm_integration_allowed: boolean;
}

export interface UpdateOrganizationType {
  address?: AddressType;
  default_currency_code?: string;
  tax_rate?: number;
  timezone?: string;
  payment_grace_period?: number;
  subscription_filter_keys?: string[];
  tax_providers?: TaxProviderType[];
}

export interface ActionUserType extends UserType {
  string_repr: string;
}

export interface Action {
  id: number;
  actor: ActionUserType;
  verb: any;
  action_object: any;
  target: any;
  public: boolean;
  description: string;
  timestamp: string;
}

export interface PaginatedActionsType {
  next: string;
  previous: string;
  results: Action[];
}
