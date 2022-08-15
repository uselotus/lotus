import axios, { AxiosResponse } from "axios";
import { CustomerType } from "../types/customer-type";
import { PlanType } from "../types/plan-type";

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 15000,
  headers: {
    Authorization: "Api-Key " + import.meta.env.VITE_API_TOKEN,
  },
});

const responseBody = (response: AxiosResponse) => response.data;

const requests = {
  get: (url: string) => instance.get(url).then(responseBody),
  post: (url: string, body: {}) => instance.post(url, body).then(responseBody),
  put: (url: string, body: {}) => instance.put(url, body).then(responseBody),
  delete: (url: string) => instance.delete(url).then(responseBody),
};

export const Customer = {
  getCustomers: (): Promise<CustomerType[]> => requests.get("api/customers"),
  getACustomer: (id: number): Promise<CustomerType> =>
    requests.get(`posts/${id}`),
  createCustomer: (post: CustomerType): Promise<CustomerType> =>
    requests.post("posts", post),
};

export const Plan = {
  getCustomers: (): Promise<CustomerType[]> => requests.get("api/customers"),
  getACustomer: (id: number): Promise<CustomerType> =>
    requests.get(`posts/${id}`),
  createCustomer: (post: CustomerType): Promise<CustomerType> =>
    requests.post("posts", post),
};
