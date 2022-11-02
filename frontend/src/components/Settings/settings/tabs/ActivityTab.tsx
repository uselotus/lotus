import React, { FC, Fragment, useState } from "react";
import { useQuery, useMutation } from "react-query";
import dayjs from "dayjs";
import { Paper } from "../../../base/Paper";
import { Typography } from "antd";

const activityItems = [
  {
    actor: {
      name: "John Doe",
      id: "123",
    },
    verb: "created",
    action_object: "v3",
    target: "plan 3",
    timestamp: "2021-01-01T00:00:00Z",
  },
  {
    actor: {
      name: "Jane Doe",
      id: "456",
    },
    verb: "created",
    action_object: "subscription",
    target: "plan",
    timestamp: "2021-01-01T00:00:00Z",
  },
];

export default function ActivityStream() {
  return (
    <Fragment>
      <Typography.Title level={2}>Activity Stream</Typography.Title>
      <div className="w-1/2 justify-center">
        <Paper border={true}>
          <ul role="list" className="divide-y divide-gray-200">
            {activityItems.map((activityItem) => (
              <li key={activityItem.actor.id} className="py-4">
                <div className="flex space-x-3">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold">{activityItem.actor.name}</h3>
                      <h3 className=" text-gray-500">
                        {dayjs(activityItem.timestamp).format(
                          "HH:MM  YYYY:MM:DD"
                        )}
                      </h3>
                    </div>
                    <h3 className="">
                      {activityItem.verb} {activityItem.action_object} on{" "}
                      {activityItem.target}
                    </h3>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Paper>
      </div>
    </Fragment>
  );
}
