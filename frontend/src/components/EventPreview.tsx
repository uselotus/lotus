// @ts-ignore
import React, { FC, useState, useEffect } from "react";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { Collapse } from "antd";
import { EventPages } from "../types/event-type";
import { Events } from "../api/api";
import LoadingSpinner from "./LoadingSpinner";
// @ts-ignore
import dayjs from "dayjs";
import "./EventPreview.css"
import CustomPagination from "./CustomPagination/CustomPagination";

const { Panel } = Collapse;

const EventPreview: FC = () => {
  const [cursor, setCursor] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [next, setNext] = useState<string>("");
  const [previous, setPrev] = useState<string>("");
  const queryClient = useQueryClient();

  const { data, isLoading }: UseQueryResult<EventPages> = useQuery<EventPages>(
    ["preview events", cursor],
    () =>
      Events.getEventPreviews(cursor).then((res) => {
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

  if ((isLoading || !data) && !cursor) {
    return (
      <div>
        <LoadingSpinner />.
      </div>
    );
  }
  if (data?.results.length === 0) {
    return (
      <div className="align-center">
        <h3 className="text-xl font-main align-center">No Events</h3>
        <div className="separator mb-5 mt-5" />
      </div>
    );
  }

  const handleMovements = (direction:"LEFT" | "RIGHT" | "START") => {
      switch (direction){
          case "LEFT":
              setCursor(previous);
              setCurrentPage(currentPage - 1)
              queryClient.invalidateQueries(["preview_events", cursor]);
              return
          case "RIGHT":
              setCursor(next);
              setCurrentPage(currentPage + 1)
              queryClient.invalidateQueries(["preview_events", cursor]);
              return;
          case "START":
              setCursor(null);
              setCurrentPage(1)
              queryClient.invalidateQueries(["preview_events", null]);
              return;
      }

  }

  return (
    <div className="w-full rounded">
      <Collapse expandIconPosition="end" bordered={false}>
          {(!data && !!cursor) && (
              <div className="loadMoreSpinner">
                  <LoadingSpinner />.
              </div>
          )}

        {data?.results.map((event) => (
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

      <CustomPagination cursor={cursor}
                        previous={previous}
                        next={next}
                        currentPage={currentPage}
                        handleMovements={handleMovements}
                        />
    </div>
  );
};

export default EventPreview;
