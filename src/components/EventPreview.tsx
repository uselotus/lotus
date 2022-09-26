import React, { FC, useState, useEffect, useRef } from "react";
import { useQuery, UseQueryResult } from "react-query";
import { List, Descriptions } from "antd";
import { EventPreviewType, EventPages } from "../types/event-type";
import { Events } from "../api/api";
import LoadingSpinner from "./LoadingSpinner";

const EventPreivew: FC = () => {
  const [page, setPage] = useState<number>(1);

  const { data, isLoading }: UseQueryResult<EventPages> = useQuery<EventPages>(
    ["preview events"],
    () =>
      Events.getEventPreviews(page).then((res) => {
        return res;
      }),
    {
      refetchInterval: 30000,
    }
  );

  if (isLoading || data === undefined) {
    return (
      <div>
        <LoadingSpinner />.
      </div>
    );
  }
  if (data.events.length === 0) {
    return (
      <div className="align-center">
        <h3 className="text-xl font-main align-center">No Events</h3>
      </div>
    );
  }
  return (
    <div>
      <List>
        {data.events.map((event) => (
          <List.Item>
            <Descriptions
              title={event.idempotency_id}
              key={event.idempotency_id}
            >
              <Descriptions.Item label="event_name">
                {event.event_name}
              </Descriptions.Item>
              <Descriptions.Item label="time_created">
                {event.time_created}
              </Descriptions.Item>
              <Descriptions.Item label="properties">
                {event.properties ? event.properties.toString() : "None"}
              </Descriptions.Item>
              <Descriptions.Item label="customer_id">
                {event.customer_id}
              </Descriptions.Item>
            </Descriptions>
          </List.Item>
        ))}
      </List>
    </div>
  );
};

export default EventPreivew;
