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
