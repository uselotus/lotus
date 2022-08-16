import axios, { AxiosResponse } from "axios";
import { CustomerType } from "../types/customer-type";
import { PlanType } from "../types/plan-type";
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
  get: (url: string) => instance.get(url).then(responseBody),
  post: (url: string, body: {}, headers?: {}) =>
    instance.post(url, body, headers).then(responseBody),
  put: (url: string, body: {}) => instance.put(url, body).then(responseBody),
  delete: (url: string) => instance.delete(url).then(responseBody),
};

export const Customer = {
  getCustomers: (): Promise<CustomerType[]> => requests.get("api/customers"),
  getACustomer: (id: number): Promise<CustomerType> =>
    requests.get(`api/customers/${id}`),
  createCustomer: (post: CustomerType): Promise<CustomerType> =>
    requests.post("api/customers", post),
};

export const Plan = {
  getPlans: (): Promise<PlanType[]> => requests.get("api/plans"),
};

export const StripeConnect = {
  getStripeConnectionStatus: (): Promise<StripeStatusType[]> =>
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
