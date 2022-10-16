export interface CreateOrgAccountType {
  username: string;
  password: string;
  email: string;
  company_name: string;
  industry: string;
  invite_token?: string;
}
