export interface WebhookTrigger {
  trigger_name: string;
}
export interface WebhookEndpoint {
  webhook_endpoint_id: string;
  name: string;
  webhook_url: URL;
  webhook_secret: string;
  triggers: WebhookTrigger[];
}

export interface WebhookEndpointCreate
  extends Omit<
    WebhookEndpoint,
    "triggers" | "webhook_secret" | "webhook_endpoint_id"
  > {
  triggers_in: string[];
}

export interface WebhookEndpointUpdate
  extends Omit<WebhookEndpoint, "triggers"> {
  triggers_in: string[];
}
