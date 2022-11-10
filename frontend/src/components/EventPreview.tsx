import React, { FC, useState, useEffect, useRef } from "react";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
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
  const queryClient = useQueryClient();

  const { data, isLoading }: UseQueryResult<EventPages> = useQuery<EventPages>(
    ["preview events", c],
    () =>
      Events.getEventPreviews(c).then((res) => {
        setNext(decodeURIComponent(res.next));
        setPrev(decodeURIComponent(res.previous));
        return res;
      }),
    {
      refetchInterval: 30000,
    }
  );

  useEffect(() => {
    if (data !== undefined) {
      setNext(decodeURIComponent(data.next));
      setPrev(decodeURIComponent(data.previous));
    }
  }, [data]);

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
        <div className="separator mb-5 mt-5" />

        <div className="flex justify-end space-x-4">
          <button
            onClick={() => {
              if (previous !== "null") {
                setCursor(previous);
                queryClient.invalidateQueries(["preview_events"]);
              }
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-6 h-6"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6.75 15.75L3 12m0 0l3.75-3.75M3 12h18"
              />
            </svg>
          </button>
          <button
            onClick={() => {
              if (next !== "null") {
                setCursor(next);
                queryClient.invalidateQueries(["preview_events"]);
              }
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-6 h-6"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3"
              />
            </svg>
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="w-full rounded">
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
      <div className="separator mb-5 mt-5" />

      <div className="flex justify-end space-x-4">
        <button
          onClick={() => {
            if (previous !== "null") {
              setCursor(previous);
              queryClient.invalidateQueries(["preview_events", c]);
            }
          }}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="w-6 h-6"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6.75 15.75L3 12m0 0l3.75-3.75M3 12h18"
            />
          </svg>
        </button>
        <button
          onClick={() => {
            if (next !== "null") {
              setCursor(next);
              queryClient.invalidateQueries(["preview_events", c]);
            }
          }}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="w-6 h-6"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default EventPreview;
