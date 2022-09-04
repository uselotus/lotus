import React, { useEffect, useState } from "react";
import { Statistic, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { GetSubscriptions } from "../../api/api";
import { useQuery } from "react-query";
import { SubscriptionTotals } from "../../types/subscription-type";

function SubscriptionStatistics(props: { range: any[] }) {
  const defaultData = {
    active_subscriptions: 234,
    cancelled_subscriptions: 6,
  };
  const { data, isLoading } = useQuery<SubscriptionTotals>(
    ["total_revenue"],
    () =>
      GetSubscriptions.getSubscriptionOverview(
        props.range[0].format("YYYY-MM-DD"),
        props.range[1].format("YYYY-MM-DD"),
        props.range[0].subtract(1, "month").format("YYYY-MM-DD"),
        props.range[1].subtract(1, "month").format("YYYY-MM-DD")
      ).then((res) => {
        return res;
      })
  );
  if (isLoading || !data) {
    return <div>Loading...</div>;
  }

  return (
    <div className="px-2 py-2">
      <h1 className="text-xl font-main font-bold mb-4">Subscriptions</h1>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <div className="flex flex-col items-center">
          <Statistic
            value={data.period_1_total_subscriptions}
            valueStyle={{
              fontSize: "1.875rem",
              lineHeight: "2.25rem",
            }}
            precision={0}
            className="text-3xl"
          />
          <p>Total Subscriptions</p>
        </div>

        <div className="flex flex-col items-center">
          <Statistic
            value={data.period_1_new_subscriptions}
            valueStyle={{
              fontSize: "1.875rem",
              lineHeight: "2.25rem",
            }}
            precision={0}
          />
          <p>New Subscriptions</p>
        </div>
      </div>
    </div>
  );
}

export default SubscriptionStatistics;
