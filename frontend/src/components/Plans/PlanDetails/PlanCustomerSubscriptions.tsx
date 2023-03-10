/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable camelcase */

import React, { FC, useCallback, useEffect, useState } from "react";
import "./PlanDetails.css";
import { Typography } from "antd";
import { useMutation, useQuery, useQueryClient } from "react-query";
import capitalize from "../../../helpers/capitalize";
import { Plan } from "../../../api/api";
import { components } from "../../../gen-types";
import createShortenedText from "../../../helpers/createShortenedText";
import Badge from "../../base/Badges/Badges";

interface PlanCustomerSubscriptionProps {
  plan_id: string;
  version_id: string;
}

const PlanCustomerSubscriptions: FC<PlanCustomerSubscriptionProps> = ({
  plan_id,
  version_id,
}) => {
  const [tableData, setTableData] = useState<
    components["schemas"]["PlanVersionHistoricalSubscription"][]
  >([]);
  const queryClient = useQueryClient();
  useQuery(
    ["plan_subscriptions_get", version_id],
    () => Plan.subscriptionsPlanVersions(version_id),
    {
      onSuccess: (data) => {
        if (tableData.length < data.length) {
          const newData = [...tableData, ...data];
          setTableData(newData);
        }
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan_id]);
      },
      refetchOnMount: "always",
    }
  );

  return (
    <div className="">
      {tableData && tableData.length > 0 ? (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
          <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px]">
            Current Subscriptions
          </Typography.Title>
          <div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          </div>
          <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
            <div className="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
              <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
                <table className="min-w-full divide-y divide-gray-300">
                  <thead className="bg-gray-50">
                    <tr>
                      <th
                        scope="col"
                        className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-table font-alliance sm:pl-6"
                      >
                        CUSTOMER ID
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-table font-alliance"
                      >
                        NAME
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-table font-alliance"
                      >
                        RENEWS
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 Inter bg-white">
                    {tableData && tableData.length > 0 ? (
                      tableData.map((info) => (
                        <tr key={info.customer_id}>
                          <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm Inter font-medium text-table-black sm:pl-6">
                            {createShortenedText(info.customer_id, false)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-table">
                            {capitalize(info.customer_name)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                            <Badge
                              className={` ${
                                !info.auto_renew
                                  ? "bg-rose-700 text-black"
                                  : "bg-emerald-100 text-black w-40"
                              }`}
                            >
                              <Badge.Content>
                                {info.auto_renew ? "Renews" : "Cancelled"}
                              </Badge.Content>
                            </Badge>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <div>No Subscriptions</div>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
          <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px]">
            Current Subscriptions
          </Typography.Title>
          <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          <div className="text-card-grey ">No subscriptions</div>
        </div>
      )}
    </div>
  );
};
export default PlanCustomerSubscriptions;
