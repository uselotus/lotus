import axios, { AxiosResponse } from "axios";
import {
  CustomerSummary,
  CustomerTableItem,
  CustomerType,
} from "../types/customer-type";
import { PlanType } from "../types/plan-type";
import { RevenueType } from "../types/revenue-type";
import { SubscriptionTotals } from "../types/subscription-type";
import { MetricUsage, MetricType } from "../types/metric-type";
import {
  StripeConnectType,
  StripeOauthType,
  StripeStatusType,
} from "../types/stripe-type";
import Cookies from "universal-cookie";

const cookies = new Cookies();

axios.defaults.headers.common["X-CSRFToken"] = cookies.get("csrftoken");

const instance = axios.create({
  timeout: 15000,
  withCredentials: true,
});

const responseBody = (response: AxiosResponse) => response.data;

const requests = {
  get: (url: string, params?: {}) =>
    instance.get(url, params).then(responseBody),
  post: (url: string, body: {}, headers?: {}) =>
    instance.post(url, body, headers).then(responseBody),
  put: (url: string, body: {}) => instance.put(url, body).then(responseBody),
  delete: (url: string) => instance.delete(url).then(responseBody),
};

export const Customer = {
  getCustomers: (): Promise<CustomerSummary> =>
    requests.get("api/customer_summary/"),
  getACustomer: (id: number): Promise<CustomerType> =>
    requests.get(`api/customers/${id}`),
  createCustomer: (post: CustomerType): Promise<CustomerType> =>
    requests.post("api/customers/", post),
};

export const Plan = {
  getPlans: (): Promise<PlanType[]> => requests.get("api/plans/"),
};

export const StripeConnect = {
  getStripeConnectionStatus: (): Promise<StripeStatusType> =>
    requests.get("api/stripe"),
  connectStripe: (authorization_code: string): Promise<StripeOauthType> =>
    requests.post("api/stripe", { authorization_code }),
};

export const Authentication = {
  getSession: (): Promise<{ isAuthenticated: boolean }> =>
    requests.get("api/session/"),
  login: (
    username: string,
    password: string
  ): Promise<{ username: string; password: string }> =>
    requests.post("api/login/", { username, password }),
};

export const GetRevenue = {
  getMonthlyRevenue: (
    period_1_end_date: string,
    period_1_start_date: string,
    period_2_start_date: string,
    period_2_end_date: string
  ): Promise<RevenueType> =>
    requests.get("api/period_metric_revenue/", {
      params: {
        period_1_end_date,
        period_1_start_date,
        period_2_start_date,
        period_2_end_date,
      },
    }),
};

export const GetSubscriptions = {
  getSubscriptionOverview: (
    period_1_end_date: string,
    period_1_start_date: string,
    period_2_start_date: string,
    period_2_end_date: string
  ): Promise<SubscriptionTotals> =>
    requests.get("api/period_subscriptions/", {
      params: {
        period_1_end_date,
        period_1_start_date,
        period_2_start_date,
        period_2_end_date,
      },
    }),
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
};
