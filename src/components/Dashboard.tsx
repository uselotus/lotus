import React, { FC } from "react";
import { Card } from "antd";
import RevenueDisplay from "./RevenueDisplay";
import SubscriptionStatistics from "./SubscriptionStatistics";
import MetricBarGraph from "./MetricBarGraph";

const Dashboard: FC = () => {
  return (
    <div>
      <h1 className="text-3xl font-main mb-10">Dashboard</h1>
      <div className="grid grid-cols-2 justify-center ">
        <Card className="max-w-lg">
          <RevenueDisplay />
        </Card>
        <Card className="max-w-lg">
          <SubscriptionStatistics />
        </Card>
      </div>
      <div>
        <MetricBarGraph />
      </div>
    </div>
  );
};

export default Dashboard;
