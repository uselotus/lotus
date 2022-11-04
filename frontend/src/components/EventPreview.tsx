import React, { FC, useState, useEffect, useRef } from "react";
import { useQuery, UseQueryResult } from "react-query";
import { List, Descriptions, Collapse } from "antd";
import { EventPreviewType, EventPages } from "../types/event-type";
import { Events } from "../api/api";
import LoadingSpinner from "./LoadingSpinner";
import dayjs from "dayjs";

const { Panel } = Collapse;

const EventPreview: FC = () => {
  const [c, setCursor] = useState<string>("");
  const [next, setNext] = useState<string>("");
  const [previous, setPrev] = useState<string>("");

  const { data, isLoading }: UseQueryResult<EventPages> = useQuery<EventPages>(
    ["preview events", c],
    () =>
      Events.getEventPreviews(c).then((res) => {
        setCursor(c);
        setNext(decodeURIComponent(res.next));
        setPrev(decodeURIComponent(res.previous));
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
  if (data.results.length === 0) {
    return (
      <div className="align-center">
        <h3 className="text-xl font-main align-center">No Events</h3>
      </div>
    );
  }
  return (
    <div className="w-full">
      <Collapse expandIconPosition="end" bordered={false}>
        {data.results.map((event) => (
          <Panel
            header={
              <div className="grid grid-cols-2">
                <p className="text-left	">event_name: {event.event_name}</p>
                <p className="text-left	">customer_id: {event.customer}</p>
              </div>
            }
            key={event.id}
          >
            <div className="grid grid-row-2">
              <div className="grid grid-cols-2">
                <p>ID: {event.idempotency_id}</p>
                <p>Properties: </p>
              </div>
              <div className="grid grid-cols-2">
                <p className="text-left	">
                  time_created:{" "}
                  {dayjs(event.time_created).format("YYYY/MM/DD HH:mm")}
                </p>
                <div className="text-left flex-col flex">
                  {event.properties &&
                    Object.keys(event.properties).map((keyName, i) => (
                      <li className="travelcompany-input" key={i}>
                        {event.properties !== undefined && (
                          <span className="input-label">
                            {keyName} : {event.properties[keyName]}{" "}
                          </span>
                        )}
                      </li>
                    ))}
                </div>
              </div>
            </div>
          </Panel>
        ))}
      </Collapse>
    </div>
  );
};

export default EventPreview;
