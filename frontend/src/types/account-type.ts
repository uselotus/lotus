import { PlanType } from "./plan-type";
import { PricingUnit } from "./pricing-unit-type";

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

export interface OrganizationType {
  organization_name: string;
  payment_provider_ids: object;
  address?: {
    city: string;
    country: string;
    line1: string;
    line2: string;
    postal_code: string;
    state: string;
  };
  users: UserType[];
  default_currency: PricingUnit;
  available_currencies: PricingUnit[];
  organization_id: string;
  plan_tags: PlanType["tags"];
  tax_rate: null | number;
  invoice_grace_period: number;
  subscription_filter_keys: [];
  current_user: { username: string };
  linked_organizations: {
    current: boolean;
    organization_id: string;
    organization_type: string;
    organization_name: string;
  }[];
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
