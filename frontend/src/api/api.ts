import axios, { AxiosResponse } from "axios";
import {
  CustomerPlus,
  CustomerType,
  CustomerTotal,
  CustomerDetailType,
} from "../types/customer-type";
import {
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
} from "../types/webhook-type";
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
} from "../types/payment-processor-type";
import { CustomerCostType, RevenueType } from "../types/revenue-type";
import {
  SubscriptionTotals,
  CreateSubscriptionType,
  UpdateSubscriptionType,
  SubscriptionType,
  CancelSubscriptionType,
  ChangeSubscriptionPlanType,
  TurnSubscriptionAutoRenewOffType,
} from "../types/subscription-type";
import { MetricUsage, MetricType, MetricNameType } from "../types/metric-type";
import { EventPages } from "../types/event-type";
import { DemoSignupProps } from "../pages/DemoSignup";
import {
  CreateOrgAccountType,
  OrganizationType,
  PaginatedActionsType,
} from "../types/account-type";
import { FeatureType } from "../types/feature-type";
import Cookies from "universal-cookie";
import {
  CreateBacktestType,
  BacktestType,
  BacktestResultType,
} from "../types/experiment-type";
import {
  OrganizationSettingsParams,
  OrganizationSettings,
  Source,
  StripeImportCustomerResponse,
  TransferSub,
  UpdateOrganizationSettingsParams,
} from "../types/stripe-type";
import { DraftInvoiceType, InvoiceType } from "../types/invoice-type";
import {
  BalanceAdjustments,
  MarkInvoiceStatusAsPaid,
} from "../types/invoice-type";
import { CreateBalanceAdjustmentType } from "../types/balance-adjustment";
import { PricingUnit } from "../types/pricing-unit-type";

import { stringify } from "qs";

const cookies = new Cookies();

axios.defaults.headers.common["Authorization"] = `Token ${cookies.get(
  "Token"
)}`;

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

const requests = {
  get: (url: string, params?: {}) =>
    instance.get(url, params).then(responseBody),
  post: (url: string, body: {}, headers?: {}) =>
    instance.post(url, body, headers).then(responseBody),
  patch: (url: string, body: {}, params?: {}) =>
    instance.patch(url, body, { params: params }).then(responseBody),
  delete: (url: string, params?: {}) =>
    instance.delete(url, { params: params }).then(responseBody),
};

export const Customer = {
  getCustomers: (): Promise<CustomerPlus[]> =>
    requests.get("api/customer_summary/"),
  getCustomerDetail: (customer_id: string): Promise<CustomerDetailType> =>
    requests.get(`api/customers/${customer_id}/`),
  createCustomer: (post: CustomerType): Promise<CustomerType> =>
    requests.post("api/customers/", post),
  getCustomerTotals: (): Promise<CustomerTotal[]> =>
    requests.get("api/customer_totals/"),
  updateCustomer: (
    customer_id: string,
    default_currency_code: string
  ): Promise<CustomerDetailType> =>
    requests.patch(`api/customers/${customer_id}/`, {
      default_currency_code: default_currency_code,
    }),
  // getCustomerDetail: (customer_id: string): Promise<CustomerDetailType> =>
  //   requests.get(`api/customer_detail/`, { params: { customer_id } }),
  //Subscription handling
  getCost(
    customer_id: string,
    start_date: string,
    end_date: string
  ): Promise<CustomerCostType> {
    return requests.get(`api/cost_analysis/`, {
      params: { customer_id, start_date, end_date },
    });
  },
  createSubscription: (
    post: CreateSubscriptionType
  ): Promise<SubscriptionType> =>
    requests.post("api/subscriptions/plans/", post),
  updateSubscription: (
    subscription_id: string,
    post: UpdateSubscriptionType,
    params?: {
      customer_id?: string;
      plan_id?: string;
      subscription_filters?: { property_name: string; value: string }[];
    }
  ): Promise<UpdateSubscriptionType> =>
    requests.patch(
      `api/subscriptions/plans/`,
      post,
      stringify(params, { encode: false })
    ),
  cancelSubscription: (
    post: CancelSubscriptionType
  ): Promise<CancelSubscriptionType> =>
    requests.delete(`api/subscriptions/plans/`, post),
  changeSubscriptionPlan: (
    post: ChangeSubscriptionPlanType,
    params?: {
      customer_id?: string;
      plan_id?: string;
      subscription_filters?: { property_name: string; value: string }[];
    }
  ): Promise<ChangeSubscriptionPlanType> =>
    requests.patch(
      `api/subscriptions/plans/`,
      post,
      stringify(params, { encode: false })
    ),
  turnSubscriptionAutoRenewOff: (
    post: TurnSubscriptionAutoRenewOffType,
    params?: {
      customer_id?: string;
      plan_id?: string;
      subscription_filters?: { property_name: string; value: string }[];
    }
  ): Promise<TurnSubscriptionAutoRenewOffType> =>
    requests.patch(
      `api/subscriptions/plans/`,
      post,
      stringify(params, { encode: false })
    ),
};

export const Plan = {
  //get methods
  getPlans: (): Promise<PlanType[]> => requests.get("api/plans/"),
  getPlan: (plan_id: string): Promise<PlanDetailType> =>
    requests.get(`api/plans/${plan_id}/`),
  //create plan
  createPlan: (post: CreatePlanType): Promise<PlanType> =>
    requests.post("api/plans/", post),
  //create plan version
  createVersion: (post: CreatePlanVersionType): Promise<PlanVersionType> =>
    requests.post("api/plan_versions/", post),
  //create plan external links
  createExternalLinks: (
    post: CreatePlanExternalLinkType
  ): Promise<InitialExternalLinks> =>
    requests.post("api/external_plan_link/", post),
  //delete plan external links
  deleteExternalLinks: (post: InitialExternalLinks): Promise<any> =>
    requests.delete(
      `api/external_plan_link/${post.external_plan_id}/?source=${post.source}`
    ),

  //update plans methods
  updatePlan: (
    plan_id: string,
    post: UpdatePlanType
  ): Promise<UpdatePlanType> => requests.patch(`api/plans/${plan_id}/`, post),
  //update plan versions methods
  updatePlanVersionDescription: (
    version_id: string,
    post: PlanVersionUpdateDescriptionType
  ): Promise<PlanVersionUpdateDescriptionType> =>
    requests.patch(`api/plan_versions/${version_id}/`, post),
  replacePlanVersionLater: (
    version_id: string,
    post: ReplaceLaterType
  ): Promise<ReplaceLaterType> =>
    requests.patch(`api/plan_versions/${version_id}/`, post),
  replacePlanVersionImmediately: (
    version_id: string,
    post: ReplaceImmediatelyType
  ): Promise<ReplaceImmediatelyType> =>
    requests.patch(`api/plan_versions/${version_id}/`, post),
  archivePlanVersion: (
    version_id: string,
    post: ArchivePlanVersionType
  ): Promise<ArchivePlanVersionType> =>
    requests.patch(`api/plan_versions/${version_id}/`, post),
};

export const Webhook = {
  getEndpoints: (): Promise<WebhookEndpoint> => requests.get("api/webhooks/"),
  createEndpoint: (post: WebhookEndpointCreate): Promise<WebhookEndpoint> =>
    requests.post("api/webhooks/", post),
  deleteEndpoint: (wh_id: string): Promise<WebhookEndpoint> =>
    requests.delete(`api/webhooks/${wh_id}/`),
  editEndpoint: (
    wh_id: number,
    post: WebhookEndpointUpdate
  ): Promise<WebhookEndpoint> => requests.patch(`api/webhooks/${wh_id}/`, post),
};

export const Authentication = {
  getSession: (): Promise<{ isAuthenticated: boolean }> =>
    requests.get("api/session/"),
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
      company_name: string;
    };
  }> => requests.post("api/login/", { username, password }),
  logout: (): Promise<{}> => requests.post("api/logout/", {}),
  registerCreate: (
    register: CreateOrgAccountType
  ): Promise<{
    detail: any;
    token: string;
    user: {
      username: string;
      email: string;
      organization_id: string;
      company_name: string;
    };
  }> =>
    requests.post("api/register/", {
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
      company_name: string;
    };
  }> => requests.post("api/demo_register/", { register }),

  resetPassword: (email: string): Promise<{ email: string }> =>
    requests.post("api/user/password/reset/init/", { email }),
  setNewPassword: (
    token: string,
    userId: string,
    password: string
  ): Promise<{ detail: any; token: string }> =>
    requests.post("api/user/password/reset/", { token, userId, password }),
};

export const Organization = {
  invite: (email: string): Promise<{ email: string }> =>
    requests.post("api/organization/invite/", { email }),
  get: (): Promise<OrganizationType[]> => requests.get("api/organizations/"),
  getActionStream: (cursor: string): Promise<PaginatedActionsType> =>
    requests.get("api/actions/", { params: { c: cursor } }),
  updateOrganization: (
    org_id: string,
    default_currency_code: string
  ): Promise<CustomerDetailType> =>
    requests.patch(`api/organizations/${org_id}/`, {
      default_currency_code: default_currency_code,
    }),
};

export const GetRevenue = {
  getMonthlyRevenue: (
    period_1_start_date: string,
    period_1_end_date: string,
    period_2_start_date: string,
    period_2_end_date: string
  ): Promise<RevenueType> =>
    requests.get("api/period_metric_revenue/", {
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
    requests.get("api/period_subscriptions/", {
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
    requests.get("api/plans_by_customer/"),
};

export const Features = {
  getFeatures: (): Promise<FeatureType[]> => requests.get("api/features/"),
  createFeature: (post: FeatureType): Promise<FeatureType> =>
    requests.post("api/features/", post),
};

export const Metrics = {
  getMetricUsage: (
    start_date: string,
    end_date: string,
    top_n_customers?: number
  ): Promise<MetricUsage> =>
    requests.get("api/period_metric_usage/", {
      params: { start_date, end_date, top_n_customers },
    }),
  getMetrics: (): Promise<MetricType[]> => requests.get("api/metrics/"),
  createMetric: (post: MetricType): Promise<MetricType> =>
    requests.post("api/metrics/", post),
  deleteMetric: (id: number): Promise<{}> =>
    requests.delete(`api/metrics/${id}`),
  archiveMetric: (id: string): Promise<{}> =>
    requests.patch(`api/metrics/${id}/`, { status: "archived" }),
};

export const Events = {
  getEventPreviews: (c: string): Promise<EventPages> =>
    requests.get("api/events/", { params: { c } }),
};

export const APIToken = {
  newAPIToken: (): Promise<{ api_key: string }> =>
    requests.get("api/new_api_key/", {}),
};

export const Backtests = {
  getBacktests: (): Promise<BacktestType[]> => requests.get("api/backtests/"),
  createBacktest: (post: CreateBacktestType): Promise<CreateBacktestType> =>
    requests.post("api/backtests/", post),
  getBacktestResults: (id: string): Promise<BacktestResultType> =>
    requests.get(`api/backtests/${id}/`),
};

export const Stripe = {
  //Import Customers
  importCustomers: (post: Source): Promise<StripeImportCustomerResponse> =>
    requests.post("api/import_customers/", post),

  //Import Payments
  importPayments: (post: Source): Promise<StripeImportCustomerResponse> =>
    requests.post("api/import_payment_objects/", post),

  //transfer Subscription
  transferSubscriptions: (
    post: TransferSub
  ): Promise<StripeImportCustomerResponse> =>
    requests.post("api/transfer_subscriptions/", post),

  //Get Organization Settings
  getOrganizationSettings: (
    data: OrganizationSettingsParams
  ): Promise<OrganizationSettings[]> =>
    requests.get("api/organization_settings/", { params: data }),

  //Update Organization Settings
  updateOrganizationSettings: (
    data: UpdateOrganizationSettingsParams
  ): Promise<OrganizationSettings> =>
    requests.patch(`api/organization_settings/${data.setting_id}/`, {
      setting_value: data.setting_value,
    }),
};

export const PaymentProcessorIntegration = {
  getPaymentProcessorConnectionStatus: (): Promise<
    PaymentProcessorStatusType[]
  > => requests.get("/api/payment_providers/"),
  connectPaymentProcessor: (
    pp_info: PaymentProcessorConnectionRequestType
  ): Promise<PaymentProcessorConnectionResponseType> =>
    requests.post("/api/payment_providers/", { pp_info }),
};

export const Invoices = {
  changeStatus: (data: MarkInvoiceStatusAsPaid): Promise<any> => {
    return requests.patch(`api/invoices/${data.invoice_id}/`, {
      payment_status: data.payment_status,
    });
  },
  getDraftInvoice: (customer_id: string): Promise<DraftInvoiceType> => {
    return requests.get("api/draft_invoice/", { params: { customer_id } });
  },
};

export const BalanceAdjustment = {
  createCredit: (post: CreateBalanceAdjustmentType): Promise<any> =>
    requests.post("api/balance_adjustments/", post),

  getCreditsByCustomer: (params: {
    customer_id: string;
    format?: string;
  }): Promise<BalanceAdjustments[]> => {
    if (params.format) {
      return requests.get(
        `api/balance_adjustments/?customer_id=${params.customer_id}?format=${params.format}`
      );
    }
    return requests.get(
      `api/balance_adjustments/?customer_id=${params.customer_id}`
    );
  },

  deleteCredit: (adjustment_id: string): Promise<any> =>
    requests.delete(`api/balance_adjustments/${adjustment_id}/`),
};

export const PricingUnits = {
  create: (post: PricingUnit): Promise<PricingUnit> =>
    requests.post("api/pricing_units/", post),

  list: (): Promise<PricingUnit[]> => requests.get(`api/pricing_units/`),
};
