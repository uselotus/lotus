/* eslint-disable react/no-array-index-key */
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
import { Table, Tag } from "antd";

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
        setTableData(data);
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
          <Table
            dataSource={tableData}
            columns={[
              {
                title: "Customer ID",
                dataIndex: "customer_id",
                key: "customer_id",
                render: (text: string) => createShortenedText(text),
              },
              {
                title: "Name",
                dataIndex: "customer_name",
                key: "customer_name",
              },
              {
                title: "Renews",
                dataIndex: "auto_renew",
                key: "auto_renew",
                render: (renews: boolean) => (
                  <div className="flex items-center">
                    {renews === true ? (
                      <Tag color="green">Renews</Tag>
                    ) : (
                      <Tag color="error">Cancelled</Tag>
                    )}
                  </div>
                ),
              },
            ]}
          />
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
