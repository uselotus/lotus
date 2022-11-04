import React, { FC, Fragment, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import dayjs from "dayjs";
import { Paper } from "../../../base/Paper";
import { Typography } from "antd";
import { Organization } from "../../../../api/api";

// const activityItems = [
//   {
//     actor: {
//       name: "John Doe",
//       id: "123",
//     },
//     verb: "created",
//     action_object: "v3",
//     target: "plan 3",
//     timestamp: "2021-01-01T00:00:00Z",
//   },
//   {
//     actor: {
//       name: "Jane Doe",
//       id: "456",
//     },
//     verb: "created",
//     action_object: "subscription",
//     target: "plan",
//     timestamp: "2021-01-01T00:00:00Z",
//   },
// ];

export default function ActivityStream() {
  const [cursor, setCursor] = useState<string>("");
  const [next, setNext] = useState("next");
  const [previous, setPrevious] = useState("previous");

  const {
    data: activityItems, // organization is the data returned from the query
    isLoading,
    isError,
  } = useQuery(["stream"], () =>
    Organization.getActionStream(cursor).then((res) => {
      return res.results;
    })
  );
  const queryClient = useQueryClient();

  return (
    <Fragment>
      <Typography.Title level={2}>Activity Stream</Typography.Title>
      <div className="w-1/2 justify-center">
        <Paper border={true}>
          <ul role="list" className="divide-y divide-gray-200">
            {activityItems?.map((activityItem) => (
              <li key={activityItem.id} className="py-4">
                <div className="flex space-x-3">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold">
                        {activityItem.actor.string_repr}
                      </h3>
                      <h3 className=" text-gray-500">
                        {dayjs(activityItem.timestamp).format(
                          "HH:MM  YYYY:MM:DD"
                        )}
                      </h3>
                    </div>
                    <h3 className="">
                      {activityItem.verb.string_repr}{" "}
                      {activityItem.action_object.string_repr} on{" "}
                      {activityItem?.target.string_repr}
                    </h3>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Paper>
        <div className="separator mb-5 mt-5" />

        <div className="flex justify-end space-x-4">
          <button
            onClick={() => {
              setCursor(previous);
              queryClient.invalidateQueries(["preview_events"]);
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
              setCursor(next);
              queryClient.invalidateQueries(["preview_events"]);
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
    </Fragment>
  );
}
