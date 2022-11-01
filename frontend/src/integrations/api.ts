import { PaymentProcessorConnectionResponseType, PaymentProcessorStatusType, PaymentProcessorConnectionRequestType } from "../types/payment-processor-type";
import axios, { AxiosResponse } from "axios";

axios.defaults.xsrfCookieName = "csrftoken";
axios.defaults.xsrfHeaderName = "X-CSRFToken";

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
  delete: (url: string, params?: {}) => instance.delete(url).then(responseBody),
};

// Define Integration APIs Here

export const PaymentProcessorIntegration = {
  getPaymentProcessorConnectionStatus: (): Promise<PaymentProcessorStatusType[]> =>
    requests.get("api/payment_providers/"),
  connectPaymentProcessor: (pp_info: PaymentProcessorConnectionRequestType): Promise<PaymentProcessorConnectionResponseType> =>
    requests.post("api/payment_providers/", { pp_info }),
};
