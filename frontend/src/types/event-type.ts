export interface EventPages {
  results: EventPreviewType[];
  next: string;
  previous: string;
}

export interface EventPreviewType {
  id: number;
  event_name: string;
  properties?: object;
  idempotency_id: string;
  time_created: string;
  customer_id: string;
}
