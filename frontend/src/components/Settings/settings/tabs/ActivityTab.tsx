import React, { FC, Fragment, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import dayjs from "dayjs";
import { Paper } from "../../../base/Paper";
import { Typography } from "antd";
import { Organization } from "../../../../api/api";

export default function ActivityStream() {
  const [cursor, setCursor] = useState<string>("");
  const [next, setNext] = useState("");
  const [previous, setPrevious] = useState("");

  const {
    data: activityItems, // organization is the data returned from the query
    isLoading,
    isError,
  } = useQuery(
    ["stream", cursor],
    () =>
      Organization.getActionStream(cursor).then((res) => {
        setNext(decodeURIComponent(res.next));
        setPrevious(decodeURIComponent(res.previous));
        return res.results;
      }),

    {
      refetchOnMount: "always",
    }
  );
  const queryClient = useQueryClient();

  useEffect(() => {
    console.log(cursor);
    queryClient.invalidateQueries("stream");
  }, [cursor]);

  return (
    <Fragment>
      <Typography.Title level={2}>Activity Stream</Typography.Title>
      <div className="w-1/2 justify-center">
        <Paper border={true}>
          <ul role="list" className="divide-y divide-gray-200">
            {activityItems?.map((activityItem) => (
              <li key={activityItem.id} className="py-4">
                <div className="flex space-x-3">
                  <div className="flex-1 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold">
                        User<b> {activityItem.actor.string_repr}</b>
                      </h3>
                      <h3 className=" text-gray-500">
                        {dayjs(activityItem.timestamp).format(
                          "YYYY/MM/DD HH:mm:ss"
                        )}
                      </h3>
                    </div>
                    <h3 className="m">
                      {activityItem.verb}{" "}
                      <b>{activityItem.action_object.string_repr}</b> (
                      {activityItem.action_object.object_type})
                      {activityItem?.target ? (
                        <h3 className="mt-1">
                          on <b>{activityItem.target.string_repr}</b> (
                          {activityItem?.target.object_type})
                        </h3>
                      ) : (
                        ""
                      )}{" "}
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
              if (previous !== null) {
                setCursor(previous);
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
              if (next !== null) {
                setCursor(next);
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
    </Fragment>
  );
}
