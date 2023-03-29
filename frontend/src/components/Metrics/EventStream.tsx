import React, { useCallback, useState, ChangeEvent, useEffect } from "react";
import { Button, Collapse } from "antd";
import {
  RightOutlined,
  LeftOutlined,
  DoubleLeftOutlined,
} from "@ant-design/icons";
import useDebounce from "../../hooks/useDebounce";
import { Events } from "../../api/api";

import { EventPages, EventPreviewType } from "../../types/event-type";

import useEventStream from "./useEventStream";
// import LoadingSpinner from "../LoadingSpinner";
import CopyText from "../base/CopytoClipboard";

const { Panel } = Collapse;

function timeSince(date: Date): string {
  const currDate = new Date();
  const seconds = Math.floor((currDate.getTime() - date.getTime()) / 1000);
  let interval = seconds / 31536000;

  if (interval > 1) {
    return Math.floor(interval) + "Y";
  }
  interval = seconds / 2592000;
  if (interval > 1) {
    return Math.floor(interval) + "M";
  }
  interval = seconds / 86400;
  if (interval > 1) {
    return Math.floor(interval) + "d";
  }
  interval = seconds / 3600;
  if (interval > 1) {
    return Math.floor(interval) + "h";
  }
  interval = seconds / 60;
  if (interval > 1) {
    return Math.floor(interval) + "m";
  }
  return Math.floor(seconds) + "s";
}

function EventInstance({ instance }: { instance: EventPreviewType }) {
  const date = new Date(instance.time_created);

  const prettyDate = (dateString: string) =>
    new Date(dateString).toLocaleString();

  return (
    <Collapse
      key={instance.idempotency_id}
      bordered={false}
      accordion={true}
      expandIcon={() => undefined}
    >
      <Panel
        id={instance.idempotency_id}
        header={
          <div className="font-alliance">
            <div className="flex flex-row justify-between">
              <span className="font-semibold">
                Event: {instance.event_name}
              </span>
              <p>{timeSince(date)}</p>
            </div>
            <div className="grid grid-cols-2">
              <div className="inline-flex text-left flex-auto">
                <span className="text-neutral-700 ">Customer ID:</span>
                <span onClick={(e) => e.stopPropagation()}>
                  <CopyText
                    className="text-neutral-500"
                    showIcon
                    textToCopy={instance.customer_id}
                  />
                </span>
              </div>
              <div className="inline-flex text-left flex-auto">
                <span className="text-neutral-700 ">Idempotency ID:</span>
                <span onClick={(e) => e.stopPropagation()}>
                  <CopyText
                    className="text-neutral-500"
                    showIcon
                    textToCopy={instance.idempotency_id}
                  />
                </span>
              </div>
            </div>
          </div>
        }
        className=""
        key={instance.id}
      >
        <div className="flex flex-row-reverse">
          <div className="text-neutral-500">
            <div>Created On</div>
            <div>{prettyDate(instance.time_created)}</div>
          </div>
          <div className="flex flex-row flex-1 ">
            <div className="w-3/4 rounded-md bg-white px-4 py-2">
              {instance.properties &&
                Object.entries(instance.properties).map(([key, val]) => (
                  <div className="flex flex-row ">
                    <div className="text-gold w-72 font-semiBold">{key}:</div>
                    <div className="text-neutral-500">{val}</div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </Panel>
    </Collapse>
  );
}

type Category = "customer" | "idempotency";

export default function EventStream() {
  // Search input
  const [category, setCategory] = useState<Category>("customer");
  const [search, setSearch] = useState("");
  const onSearchChange = (e: ChangeEvent<HTMLInputElement>) =>
    setSearch(e.target.value);

  const searchDebounce = useDebounce(search, 500);

  // Handles pages
  const { pageIndex, page, streaming, next, prev, start, setStreaming } =
    useEventStream({
      stream: true,
      query: {
        customer_id: category === "customer" ? searchDebounce : "",
        idempotency_id: category === "idempotency" ? searchDebounce : "",
      },
    });
  const streamBtnOnClick = () => setStreaming(!streaming);

  //cD0yMDIzLTAzLTI0KzEyJTNBNDglM0EwMS40Njg4NTIlMkIwMCUzQTAw&customer_id=cust_49e6e86ee38249bca8df1cfc64ff7913&idempotency_id=

  return (
    <>
      <div className="flex flex-row pt-10 justify-between my-4">
        <h1 className="text-2xl font-main mb-5">
          Event Stream{" "}
          <span className="text-neutral-400 text-sm">
            (recent events first)
          </span>
        </h1>
        <div className="flex flex-row gap-6">
          <div className="flex flex-row divide-x-2 divide-neutral-400">
            <input
              type="text"
              className="w-192 p-2 pl-8 z-10 rounded-l-md border border-background bg-background focus:outline-none focus:ring-2 focus:ring-yellow-600 focus:border-transparent"
              placeholder="Search..."
              value={search}
              onChange={onSearchChange}
            />
            <div className="flex flex-col relative rounded-r-md items-center bg-background">
              <select
                onChange={(e) => setCategory(e.target.value as Category)}
                className="h-full border-0 border-yellow-600 outline-1 rounded-r-md bg-background py-0 px-2 pr-7 text-gray-500 focus:ring-2 focus:ring-inset focus:ring-yellow-600 sm:text-sm focus:border-transparent target:ring-yellow-600 focus-visible:outline-yellow-600 visited:ring-yellow-600 accent-yellow-600"
              >
                <option value="customer">Customer ID</option>
                <option value="idempotency">Idempotency ID</option>
              </select>
            </div>
          </div>
          <Button
            type="primary"
            size="large"
            id="create-metric-button"
            disabled={(import.meta as any).env.VITE_IS_DEMO === "true"}
            key={"create-plan"}
            className="hover:!bg-primary-700"
            onClick={streamBtnOnClick}
            style={{ background: "#C3986B", borderColor: "#C3986B" }}
          >
            <div className="flex items-center  justify-between text-white">
              <div>{streaming ? "Stop Streaming" : "Start Streaming"}</div>
            </div>
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 divide-y rounded-xl bg-background">
        {page.map((event) => (
          <div className="mx-8">
            <EventInstance instance={event} />
          </div>
        ))}
      </div>
      <div className="flex justify-center space-x-4">
        <button
          type="button"
          className="movementButton"
          onClick={() => start()}
        >
          <DoubleLeftOutlined />
        </button>
        <button
          disabled={pageIndex === 0}
          type="button"
          className="movementButton"
          onClick={() => prev()}
        >
          <LeftOutlined />
        </button>
        <div className="currentPageNumber"> {pageIndex} </div>
        <button type="button" className="movementButton" onClick={() => next()}>
          <RightOutlined />
        </button>
      </div>
    </>
  );
}
