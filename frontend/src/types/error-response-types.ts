export interface ErrorResponse {
  type: URL;
  title: string;
  detail: string;
  validation_errors?: ValidationError[];
}

export interface ValidationError {
  code: string;
  detail: string;
  attr: string;
}
export type QueryErrors = {
  response: Resp;
};
interface Resp extends Response {
  data: {
    [key: string]: string;
  };
}
interface response extends Response {
  data: ErrorResponse
}
export interface ErrorResponseMessage extends Response {
  response: response
}
