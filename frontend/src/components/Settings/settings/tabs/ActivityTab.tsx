import React, { FC, Fragment, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import dayjs from "dayjs";
import { Paper } from "../../../base/Paper";
import { Typography } from "antd";
import { Organization } from "../../../../api/api";
import LoadingSpinner from "../../../LoadingSpinner";
import CustomPagination from "../../../CustomPagination/CustomPagination";
import {ActionUserType} from "../../../../types/account-type";

export default function ActivityStream() {
  const [cursor, setCursor] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
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
        return res;
      }),

    {
      refetchOnMount: "always",
    }
  );
  const queryClient = useQueryClient();

  useEffect(() => {
    if (activityItems !== undefined) {
      setNext(decodeURIComponent(activityItems.next));
      setPrevious(decodeURIComponent(activityItems.previous));
    }
  }, [activityItems]);

  if ((isLoading || !activityItems) && !cursor) {
    return (
      <Fragment>
        <Typography.Title level={2}>Activity Stream</Typography.Title>
        <LoadingSpinner />.
      </Fragment>
    );
  }
  if (
    activityItems?.results === undefined ||
    activityItems?.results.length === 0
  ) {
    return (
      <Fragment>
        <Typography.Title level={2}>Activity Stream</Typography.Title>
        <div className="align-center">
          <h3 className="text-xl font-main align-center">No Activities</h3>
          <div className="separator mb-5 mt-5" />
        </div>
      </Fragment>
    );
  }

  const handleMovements = (direction: "LEFT" | "RIGHT" | "START") => {
    switch (direction) {
      case "LEFT":
        if (currentPage == 1) return;
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
                        User<b> {activityItem.actor?.string_repr}</b>
                      </h3>
                      <h3 className=" text-gray-500">
                        {dayjs(activityItem.timestamp).format(
                          "YYYY/MM/DD HH:mm:ss"
                        )}
                      </h3>
                    </div>
                    <h3 className="m">
                      {activityItem.verb}{" "}
                      <b>{activityItem.action_object?.string_repr}</b> (
                      {activityItem.action_object?.object_type})
                      {activityItem?.target ? (
                        <h3 className="mt-1">
                          on <b>{activityItem.target?.string_repr}</b> (
                          {activityItem?.target?.object_type})
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

        {!activityItems && !!cursor && (
          <div className="loadMoreSpinner">
            <LoadingSpinner />.
          </div>
        )}

        <div className="separator mb-5 mt-5" />

        <CustomPagination
          cursor={cursor}
          previous={previous}
          next={next}
          currentPage={currentPage}
          handleMovements={handleMovements}
        />
      </div>
    </Fragment>
  );
}
