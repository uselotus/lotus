// @ts-ignore
import React, { FC, useState, useEffect, Fragment } from "react";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { Button, Collapse, Divider } from "antd";
import { EventPages } from "../types/event-type";
import { Events } from "../api/api";
import LoadingSpinner from "./LoadingSpinner";
// @ts-ignore
import dayjs from "dayjs";
import "./EventPreview.css";
import CustomPagination from "./CustomPagination/CustomPagination";
import CopyText from "./base/CopytoClipboard";

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

  const handleMovements = (direction: "LEFT" | "RIGHT" | "START") => {
    switch (direction) {
      case "LEFT":
        setCursor(previous);
        setCurrentPage(currentPage - 1);
        queryClient.invalidateQueries(["preview_events", cursor]);
        return;
      case "RIGHT":
        setCursor(next);
        setCurrentPage(currentPage + 1);
        queryClient.invalidateQueries(["preview_events", cursor]);
        return;
      case "START":
        setCursor(null);
        setCurrentPage(1);
        queryClient.invalidateQueries(["preview_events", null]);
        return;
    }
  };

  return (
    <Fragment>
      <div className="flex justify-between mb-4">
        <h1 className="text-2xl font-main mb-5">
          Event Stream (recent events first)
        </h1>
        <Button
          onClick={() => {
            queryClient.invalidateQueries("preview events");
          }}
          loading={isLoading}
        >
          Refresh
        </Button>
      </div>
      <Divider />

      {data?.results.length === 0 ? (
        <div className="align-center">
          <h3 className="text-xl font-main align-center">No Events</h3>
          <div className="separator mb-5 mt-5" />
        </div>
      ) : (
        <div className="w-full rounded border border-[#1d1d1f]">
          <Collapse
            expandIconPosition="end"
            bordered={false}
            className="hover:bg-background"
            style={{ background: "#ffffff" }}
          >
            {!data && !!cursor && (
              <div className="loadMoreSpinner">
                <LoadingSpinner />.
              </div>
            )}

            {data?.results.map((event) => (
              <Panel
                header={
                  <div className="grid grid-cols-2 my-2">
                    <div className="flex align-middle text-[16px] ">
                      <p className="leading-[24px]">event_name: </p>
                      <p className="infoValue"> {event.event_name}</p>
                    </div>
                    <div className="flex align-middle text-[16px]">
                      <p className="leading-[24px]">customer_id: </p>
                      <p className="infoValue"> <CopyText textToCopy={event.customer_id}/></p>
                    </div>
                  </div>
                }
                className=" hover:bg-background"
                key={event.id}
              >
                <div className="grid grid-row-2">
                  <div className="grid grid-cols-2">
                    <div className="flex align-middle text-[16px] ">
                      <p className="leading-[24px]">ID: </p>
                      <p className="infoValue">  <CopyText textToCopy={event.idempotency_id}/></p>
                    </div>

                    <p className="text-[16px]">Properties: </p>
                  </div>
                  <div className="grid grid-cols-2">
                    <div className="flex align-middle text-[16px] text-left">
                      <p className="leading-[24px]">time_created: </p>
                      <p className="infoValue">
                        {" "}
                        {dayjs(event.time_created).format(
                          "YYYY/MM/DD HH:mm:ss"
                        )}
                      </p>
                    </div>
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

          <CustomPagination
            cursor={cursor}
            previous={previous}
            next={next}
            currentPage={currentPage}
            handleMovements={handleMovements}
          />
        </div>
      )}
    </Fragment>
  );
};

export default EventPreview;
