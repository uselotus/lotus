export interface EventPages {
  events: EventPreviewType[];
  total_pages: number;
}

export interface EventPreviewType {
  id: number;
  event_name: string;
  properties?: object;
  idempotency_id: string;
  time_created: string;
  customer: number;
}
