export interface ValidationError {
  code: string;
  detail: string;
  attr: string;
}
export interface ErrorResponse {
  type: URL;
  title: string;
  detail: string;
  validation_errors?: ValidationError[];
}
interface Resp extends Response {
  data: {
    [key: string]: string;
  };
}
export type QueryErrors = {
  response: Resp;
};

interface response extends Response {
  data: ErrorResponse;
}
export interface ErrorResponseMessage extends Response {
  response: response;
}
export interface r {
  response: ErrorResponse;
}
