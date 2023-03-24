import React, {
  FormEvent,
  startTransition,
  useState,
  ChangeEvent,
  useEffect,
} from "react";
import { Button, Collapse, Divider } from "antd";
import {
  RightOutlined,
  LeftOutlined,
  DoubleLeftOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { Events } from "../../api/api";

import { EventPreviewType } from "../../types/event-type";

import useEventStream from "./useEventStream";
import LoadingSpinner from "../LoadingSpinner";
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

export default function EventStream() {
  const { pageIndex, page, streaming, next, prev, start, setStreaming } =
    useEventStream({
      stream: true,
    });

  const [search, setSearch] = useState("");
  const onSearchChange = (e: ChangeEvent<HTMLInputElement>) =>
    setSearch(e.target.value);

  const streamBtnOnClick = () => setStreaming(!streaming);

  useEffect(() => {
    Events.searchEventPreviews(
      "cust_19c63d7f99cf46f3b29dd082a44c5f5d",
      ""
    ).then((res) => console.log(res));
  }, []);

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
          <input
            type="text"
            className="w-192 p-2 pl-8 rounded-md border border-background bg-background focus:outline-none focus:ring-2 focus:ring-yellow-600 focus:border-transparent"
            placeholder="Search..."
            value={search}
            onChange={onSearchChange}
          />
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
