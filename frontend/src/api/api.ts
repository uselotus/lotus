import axios, { AxiosResponse } from "axios";
import Cookies from "universal-cookie";
import {
  CustomerType,
  CustomerTotal,
  CustomerCreateType,
  CustomerSummary,
} from "../types/customer-type";
import { AddonType, CreateAddonType } from "../types/addon-type";
import {
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
} from "../types/webhook-type";
import {
  APIKeyType,
  APIKeyCreate,
  APIKeyCreateResponse,
} from "../types/apikey-type";
import {
  PlanType,
  CreatePlanType,
  UpdatePlanType,
  PlansByCustomerArray,
  CreatePlanVersionType,
  PlanDetailType,
  PlanVersionType,
  ReplaceLaterType,
  ReplaceImmediatelyType,
  ArchivePlanVersionType,
  PlanVersionUpdateDescriptionType,
  CreatePlanExternalLinkType,
  InitialExternalLinks,
} from "../types/plan-type";
import {
  PaymentProcessorConnectionResponseType,
  PaymentProcessorStatusType,
  PaymentProcessorConnectionRequestType,
  PaymentProcessorSettingsParams,
  PaymentProcessorSetting,
  Source,
  PaymentProcessorImportCustomerResponse,
  TransferSub,
  UpdatePaymentProcessorSettingParams,
} from "../types/payment-processor-type";
import { CustomerCostType, RevenueType } from "../types/revenue-type";
import {
  SubscriptionTotals,
  CreateSubscriptionType,
  UpdateSubscriptionType,
  SubscriptionType,
  CancelSubscriptionQueryParams,
  CancelSubscriptionBody,
  ChangeSubscriptionPlanType,
  TurnSubscriptionAutoRenewOffType,
  CreateSubscriptionAddOnBody,
  CreateSubscriptionAddOnType,
  CancelCreateSubscriptionAddOnBody,
  CancelCreateSubscriptionAddOnQueryParams,
} from "../types/subscription-type";
import {
  MetricUsage,
  MetricType,
  CreateMetricType,
} from "../types/metric-type";
import { EventPages } from "../types/event-type";
import { DemoSignupProps } from "../pages/DemoSignup";
import {
  CreateOrgAccountType,
  OrganizationType,
  PaginatedActionsType,
  UpdateOrganizationPPType,
  UpdateOrganizationType,
} from "../types/account-type";
import { FeatureType, CreateFeatureType } from "../types/feature-type";
import {
  CreateBacktestType,
  BacktestType,
  BacktestResultType,
} from "../types/experiment-type";
import {
  DraftInvoiceType,
  InvoiceType,
  MarkPaymentStatusAsPaid,
} from "../types/invoice-type";
import { CreateCreditType, CreditType } from "../types/balance-adjustment";
import { CurrencyType } from "../types/pricing-unit-type";
import { AlertType, CreateAlertType } from "../types/alert-type";

const cookies = new Cookies();

axios.defaults.headers.common.Authorization = `Token ${cookies.get("Token")}`;

// @ts-ignore
const API_HOST = import.meta.env.VITE_API_URL;

axios.defaults.baseURL = API_HOST;
// axios.defaults.xsrfCookieName = "csrftoken";
// axios.defaults.xsrfHeaderName = "X-CSRFToken";

export const instance = axios.create({
  timeout: 15000,
  withCredentials: true,
});
// add a param serializer to axios that encodes using the qs library, with the option to encode set to false
// this allows us to pass in arrays as query params without them being encoded

const responseBody = (response: AxiosResponse) => response.data;

// make a function that takes an object as input and if it finds a key with the name subscription_filters, it json encodes it, and then returns the whole object
const encodeSubscriptionFilters = (obj: any) => {
  if (obj.subscription_filters) {
    obj.subscription_filters = JSON.stringify(obj.subscription_filters);
  }
  return obj;
};

const requests = {
  get: (url: string, params?: {}) =>
    instance.get(url, params).then(responseBody),
  post: (url: string, body: {}, params?: {}) =>
    instance.post(url, body, { params }).then(responseBody),
  patch: (url: string, body: {}, params?: {}) =>
    instance.patch(url, body, { params }).then(responseBody),
  delete: (url: string, params?: {}) =>
    instance.delete(url, { params }).then(responseBody),
};

export const Customer = {
  getCustomers: (): Promise<CustomerSummary[]> =>
    requests.get("app/customers/summary/"),
  getCustomerDetail: (customer_id: string): Promise<CustomerType> =>
    requests.get(`app/customers/${customer_id}/`),
  createCustomer: (post: CustomerCreateType): Promise<CustomerType> =>
    requests.post("app/customers/", post),
  getCustomerTotals: (): Promise<CustomerTotal[]> =>
    requests.get("app/customers/totals/"),
  updateCustomer: (
    customer_id: string,
    default_currency_code: string,
    shipping_address: CustomerType["shipping_address"],
    billing_address: CustomerType["billing_address"],
    tax_rate: number,
    timezone: string
  ): Promise<CustomerType> =>
    requests.patch(`app/customers/${customer_id}/`, {
      default_currency_code,
      shipping_address,
      billing_address,
      tax_rate,
      timezone,
    }),
  // getCustomerDetail: (customer_id: string): Promise<CustomerDetailType> =>
  //   requests.get(`app/customer_detail/`, { params: { customer_id } }),
  // Subscription handling
  getCost(
    customer_id: string,
    start_date: string,
    end_date: string
  ): Promise<CustomerCostType> {
    return requests.get(`app/cost_analysis/`, {
      params: { customer_id, start_date, end_date },
    });
  },
  createSubscription: (
    post: CreateSubscriptionType
  ): Promise<SubscriptionType> => requests.post("app/subscriptions/add/", post),
  updateSubscription: (
    post: UpdateSubscriptionType,
    params?: {
      customer_id?: string;
      plan_id?: string;
      subscription_filters?: { property_name: string; value: string }[];
    }
  ): Promise<UpdateSubscriptionType> =>
    requests.post(`app/subscriptions/update/`, post, params),
  cancelSubscription: (
    params: CancelSubscriptionQueryParams,
    post: CancelSubscriptionBody
  ): Promise<SubscriptionType> =>
    requests.post(`app/subscriptions/cancel/`, post, params),
  changeSubscriptionPlan: (
    post: ChangeSubscriptionPlanType,
    params?: {
      customer_id?: string;
      plan_id?: string;
      subscription_filters?: { property_name: string; value: string }[];
    }
  ): Promise<SubscriptionType> =>
    requests.post(`app/subscriptions/update/`, post, params),
  turnSubscriptionAutoRenewOff: (
    post: TurnSubscriptionAutoRenewOffType,
    params?: {
      customer_id?: string;
      plan_id?: string;
      subscription_filters?: { property_name: string; value: string }[];
    }
  ): Promise<SubscriptionType> =>
    requests.post(`app/subscriptions/update/`, post, params),
  createSubscriptionAddOns: (
    body: CreateSubscriptionAddOnBody
  ): Promise<CreateSubscriptionAddOnType> =>
    requests.post(`app/subscriptions/addons/add/`, body),
  cancelCreateSubscriptionAddOns: (
    body: CancelCreateSubscriptionAddOnBody,
    params: CancelCreateSubscriptionAddOnQueryParams
  ): Promise<CreateSubscriptionAddOnType[]> =>
    requests.post(`app/subscriptions/addons/cancel/`, body, params),
};

export const Addon = {
  getAddons: (): Promise<AddonType[]> => requests.get("app/addons/"),
  getAddon: (addon_id: string): Promise<AddonType> =>
    requests.get(`app/addons/${addon_id}/`),
  createAddon: (post: CreateAddonType): Promise<AddonType> =>
    requests.post("app/addons/", post),
};

export const Plan = {
  // get methods
  getPlans: (): Promise<PlanType[]> => requests.get("app/plans/"),
  getPlan: (plan_id: string): Promise<PlanDetailType> =>
    requests.get(`app/plans/${plan_id}/`),
  // create plan
  createPlan: (post: CreatePlanType): Promise<PlanType> =>
    requests.post("app/plans/", post),
  // create plan version
  createVersion: (post: CreatePlanVersionType): Promise<PlanVersionType> =>
    requests.post("app/plan_versions/", post),
  // create plan external links
  createExternalLinks: (
    post: CreatePlanExternalLinkType
  ): Promise<InitialExternalLinks> =>
    requests.post("app/external_plan_links/", post),
  // delete plan external links
  deleteExternalLinks: (post: InitialExternalLinks): Promise<any> =>
    requests.delete(
      `app/external_plan_links/${post.external_plan_id}/?source=${post.source}`
    ),

  // update plans methods
  updatePlan: (
    plan_id: string,
    post: UpdatePlanType
  ): Promise<UpdatePlanType> => requests.patch(`app/plans/${plan_id}/`, post),
  // update plan versions methods
  updatePlanVersionDescription: (
    version_id: string,
    post: PlanVersionUpdateDescriptionType
  ): Promise<PlanVersionUpdateDescriptionType> =>
    requests.patch(`app/plan_versions/${version_id}/`, post),
  replacePlanVersionLater: (
    version_id: string,
    post: ReplaceLaterType
  ): Promise<ReplaceLaterType> =>
    requests.patch(`app/plan_versions/${version_id}/`, post),
  replacePlanVersionImmediately: (
    version_id: string,
    post: ReplaceImmediatelyType
  ): Promise<ReplaceImmediatelyType> =>
    requests.patch(`app/plan_versions/${version_id}/`, post),
  archivePlanVersion: (
    version_id: string,
    post: ArchivePlanVersionType
  ): Promise<ArchivePlanVersionType> =>
    requests.patch(`app/plan_versions/${version_id}/`, post),
  createAlert: (post: CreateAlertType): Promise<AlertType> =>
    requests.post("app/usage_alerts/", post),
  deleteAlert: (post: { usage_alert_id: string }): Promise<AlertType> =>
    requests.delete(`app/usage_alerts/${post.usage_alert_id}/`),
};

export const Webhook = {
  getEndpoints: (): Promise<WebhookEndpoint> => requests.get("app/webhooks/"),
  createEndpoint: (post: WebhookEndpointCreate): Promise<WebhookEndpoint> =>
    requests.post("app/webhooks/", post),
  deleteEndpoint: (wh_id: string): Promise<WebhookEndpoint> =>
    requests.delete(`app/webhooks/${wh_id}/`),
  editEndpoint: (
    wh_id: number,
    post: WebhookEndpointUpdate
  ): Promise<WebhookEndpoint> => requests.patch(`app/webhooks/${wh_id}/`, post),
};

export const APIKey = {
  getKeys: (): Promise<APIKeyType[]> => requests.get("app/api_tokens/"),
  createKey: (post: APIKeyCreate): Promise<APIKeyCreateResponse> =>
    requests.post("app/api_tokens/", post),
  deleteKey: (prefix: string): Promise<any> =>
    requests.delete(`app/api_tokens/${prefix}/`),
  rollKey: (prefix: string): Promise<APIKeyCreateResponse> =>
    requests.post(`app/api_tokens/${prefix}/roll/`, {}),
};

export const Authentication = {
  getSession: (): Promise<{ isAuthenticated: boolean }> =>
    requests.get("app/session/"),
  login: (
    username: string,
    password: string
  ): Promise<{
    detail: any;
    token: string;
    user: {
      username: string;
      email: string;
      organization_id: string;
      organization_name: string;
    };
  }> => requests.post("app/login/", { username, password }),
  demo_login: (
    username: string,
    password: string
  ): Promise<{
    detail: any;
    token: string;
    user: {
      username: string;
      email: string;
      organization_id: string;
      organization_name: string;
    };
  }> => requests.post("app/demo_login/", { username, password }),
  logout: (): Promise<{}> => requests.post("app/logout/", {}),
  registerCreate: (
    register: CreateOrgAccountType
  ): Promise<{
    detail: any;
    token: string;
    user: {
      username: string;
      email: string;
      organization_id: string;
      organization_name: string;
    };
  }> =>
    requests.post("app/register/", {
      register,
    }),
  registerDemo: (
    register: DemoSignupProps
  ): Promise<{
    detail: any;
    token: string;
    user: {
      username: string;
      email: string;
      organization_id: string;
      organization_name: string;
    };
  }> => requests.post("app/demo_register/", { register }),

  resetPassword: (email: string): Promise<{ email: string }> =>
    requests.post("app/user/password/reset/init/", { email }),
  setNewPassword: (
    token: string,
    userId: string,
    password: string
  ): Promise<{ detail: any; token: string }> =>
    requests.post("app/user/password/reset/", { token, userId, password }),
};

export const Organization = {
  invite: (email: string): Promise<{ email: string }> =>
    requests.post("app/organization/invite/", { email }),
  invite_link: (email: string): Promise<{ email: string }> =>
    requests.post("app/organization/invite_link/", { email }),
  get: (): Promise<OrganizationType[]> => requests.get("app/organizations/"),
  createOrg: (
    organization_name: string,
    default_currency_code: string,
    organization_type: "development" | "production"
  ): Promise<OrganizationType> =>
    requests.post("app/organizations/", {
      organization_name,
      default_currency_code,
      organization_type,
    }),
  switchOrg: (org_id: string): Promise<OrganizationType> =>
    requests.post("/app/switch_organization/", {
      transfer_to_organization_id: org_id,
    }),
  getActionStream: (cursor: string): Promise<PaginatedActionsType> =>
    requests.get("app/actions/", { params: { c: cursor } }),
  updateOrganization: (
    org_id: string,
    input: UpdateOrganizationType
  ): Promise<OrganizationType> =>
    requests.patch(`app/organizations/${org_id}/`, input),
  updateOrganizationPaymentProvider: (
    data: UpdateOrganizationPPType
  ): Promise<OrganizationType> => {
    const { org_id, ...payload } = data;
    return requests.patch(`app/organizations/${org_id}/`, { ...payload });
  },
};

export const GetRevenue = {
  getMonthlyRevenue: (
    period_1_start_date: string,
    period_1_end_date: string,
    period_2_start_date: string,
    period_2_end_date: string
  ): Promise<RevenueType> =>
    requests.get("app/period_metric_revenue/", {
      params: {
        period_1_start_date,
        period_1_end_date,
        period_2_start_date,
        period_2_end_date,
      },
    }),
};

export const GetSubscriptions = {
  getSubscriptionOverview: (
    period_1_start_date: string,
    period_1_end_date: string,
    period_2_start_date: string,
    period_2_end_date: string
  ): Promise<SubscriptionTotals> =>
    requests.get("app/period_subscriptions/", {
      params: {
        period_1_start_date,
        period_1_end_date,
        period_2_start_date,
        period_2_end_date,
      },
    }),
};

export const PlansByCustomer = {
  getPlansByCustomer: (): Promise<PlansByCustomerArray> =>
    requests.get("app/plans_by_customer/"),
};

export const Features = {
  getFeatures: (): Promise<FeatureType[]> => requests.get("app/features/"),
  createFeature: (post: CreateFeatureType): Promise<FeatureType> =>
    requests.post("app/features/", post),
};

export const Metrics = {
  getMetricUsage: (
    start_date: string,
    end_date: string,
    top_n_customers?: number
  ): Promise<MetricUsage> =>
    requests.get("app/period_metric_usage/", {
      params: { start_date, end_date, top_n_customers },
    }),
  getMetrics: (): Promise<MetricType[]> => requests.get("app/metrics/"),
  createMetric: (post: CreateMetricType): Promise<MetricType> =>
    requests.post("app/metrics/", post),
  deleteMetric: (id: number): Promise<{}> =>
    requests.delete(`app/metrics/${id}`),
  archiveMetric: (id: string): Promise<{}> =>
    requests.patch(`app/metrics/${id}/`, { status: "archived" }),
};

export const Events = {
  getEventPreviews: (c: string): Promise<EventPages> =>
    requests.get("app/events/", { params: { c } }),
  getEventCount: (
    period_1_start_date: string,
    period_1_end_date: string,
    period_2_start_date: string,
    period_2_end_date: string
  ): Promise<{
    total_events_period_1: number;
    total_events_period_2: number;
  }> =>
    requests.get("app/period_events/", {
      params: {
        period_1_start_date,
        period_1_end_date,
        period_2_start_date,
        period_2_end_date,
      },
    }),
};

export const APIToken = {
  newAPIToken: (): Promise<{ api_key: string }> =>
    requests.get("app/new_api_key/", {}),
};

export const Backtests = {
  getBacktests: (): Promise<BacktestType[]> => requests.get("app/backtests/"),
  createBacktest: (post: CreateBacktestType): Promise<CreateBacktestType> =>
    requests.post("app/backtests/", post),
  getBacktestResults: (id: string): Promise<BacktestResultType> =>
    requests.get(`app/backtests/${id}/`),
};

export const PaymentProcessor = {
  // Import Customers
  importCustomers: (
    post: Source
  ): Promise<PaymentProcessorImportCustomerResponse> =>
    requests.post("app/import_customers/", post),

  // Import Payments
  importPayments: (
    post: Source
  ): Promise<PaymentProcessorImportCustomerResponse> =>
    requests.post("app/import_payment_objects/", post),

  // transfer Subscription
  transferSubscriptions: (
    post: TransferSub
  ): Promise<PaymentProcessorImportCustomerResponse> =>
    requests.post("app/transfer_subscriptions/", post),

  // Get Stripe Setting
  getPaymentProcessorSettings: (
    data: PaymentProcessorSettingsParams
  ): Promise<PaymentProcessorSetting[]> =>
    requests.get("app/organization_settings/", { params: data }),

  // Update Stripe Setting
  updatePaymentProcessorSetting: (
    data: UpdatePaymentProcessorSettingParams
  ): Promise<PaymentProcessorSetting> =>
    requests.patch(`app/organization_settings/${data.setting_id}/`, {
      setting_values: data.setting_values,
    }),
};

export const PaymentProcessorIntegration = {
  getPaymentProcessorConnectionStatus: (): Promise<
    PaymentProcessorStatusType[]
  > => requests.get("app/payment_providers/"),
  connectPaymentProcessor: (
    pp_info: PaymentProcessorConnectionRequestType
  ): Promise<PaymentProcessorConnectionResponseType> =>
    requests.post("app/payment_providers/", { pp_info }),
};

export const Invoices = {
  changeStatus: (data: MarkPaymentStatusAsPaid): Promise<any> =>
    requests.patch(`app/invoices/${data.invoice_id}/`, {
      payment_status: data.payment_status,
    }),
  sendToPaymentProcessor: (invoice_id: string): Promise<InvoiceType> =>
    requests.post(`app/invoices/${invoice_id}/send`, {}),
  getDraftInvoice: (customer_id: string): Promise<DraftInvoiceType> =>
    requests.get("app/draft_invoice/", { params: { customer_id } }),
  getInvoiceUrl: (invoice_id: string): Promise<{ url: string }> =>
    requests.get(`app/invoices/${invoice_id}/pdf_url/`),
};

export const Credits = {
  createCredit: (post: CreateCreditType): Promise<CreditType> =>
    requests.post("app/credits/", post),

  getCreditsByCustomer: (params: {
    customer_id: string;
    format?: string;
  }): Promise<CreditType[]> => {
    if (params.format) {
      return requests.get(
        `app/credits/?customer_id=${params.customer_id}?format=${params.format}`
      );
    }
    return requests.get(`app/credits/?customer_id=${params.customer_id}`);
  },

  deleteCredit: (credit_id: string): Promise<CreditType> =>
    requests.post(`app/credits/${credit_id}/void/`, {}),
};

export const PricingUnits = {
  create: (post: CurrencyType): Promise<CurrencyType> =>
    requests.post("app/pricing_units/", post),

  list: (): Promise<CurrencyType[]> => requests.get(`app/pricing_units/`),
};
