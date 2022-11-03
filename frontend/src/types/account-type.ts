export interface CreateOrgAccountType {
  username: string;
  password: string;
  email: string;
  company_name: string;
  industry: string;
  invite_token?: string;
}

export interface UserType {
  username: string;
  email: string;
  role: string;
  status: string;
}

export interface OrganizationType {
  company_name: string;
  payment_plan: string;
  payment_provider_ids: object;
  users: UserType[];
}
