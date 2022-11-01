import React, { useEffect, useState } from "react";
import { Statistic, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { GetSubscriptions } from "../../api/api";
import { useQuery } from "react-query";
import { SubscriptionTotals } from "../../types/subscription-type";
import { Paper } from "../base/Paper";

function SubscriptionStatistics(props: { range: any[] }) {
  const defaultData = {
    active_subscriptions: 234,
    cancelled_subscriptions: 6,
  };
  const { data, isLoading } = useQuery<SubscriptionTotals>(
    ["subscription_overview", props.range],
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
    <Paper border={true} color="white">
      <h1 className="text-base font-normal mb-4">Subscriptions</h1>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <div className="flex items-center">
          <h2 className="text-3xl px-0 my-0 pr-4">
            {data.period_1_total_subscriptions}
          </h2>
          <span>Total</span>
        </div>
        <div className="flex items-center">
          <h2 className="text-3xl px-0 my-0 pr-4">
            {data.period_1_new_subscriptions}
          </h2>
          <span>New</span>
        </div>
      </div>
    </Paper>
  );
}

export default SubscriptionStatistics;
