import React, { useEffect, useState } from "react";
import { Statistic, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

function SubscriptionStatistics() {
  const defaultData = {
    active_subscriptions: 34234,
    cancelled_subscriptions: 324,
  };
  const [subscriptions, setSubscriptions] = useState<any>(defaultData);

  //   useEffect(() => {
  //     GetRevenue.getMonthlyRevenue().then((data) => {
  //       if (data) {
  //         setRevenueData(data);
  //       }
  //     });
  //   }, []);
  return (
    <div className="px-2 py-2">
      <h1 className="text-xl font-main font-bold mb-4">Subscriptions</h1>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <div className="flex flex-col items-center">
          <Statistic
            value={subscriptions.active_subscriptions}
            valueStyle={{
              fontSize: "1.875rem",
              lineHeight: "2.25rem",
            }}
            precision={2}
            className="text-3xl"
          />
          <h1>Active Subscriptions</h1>
        </div>

        <div className="flex flex-col items-center">
          <Statistic
            value={subscriptions.cancelled_subscriptions}
            valueStyle={{
              fontSize: "1.875rem",
              lineHeight: "2.25rem",
            }}
            precision={2}
            suffix="%"
          />
          <h1>Cancelled Subscriptions</h1>
        </div>
      </div>
    </div>
  );
}

export default SubscriptionStatistics;
