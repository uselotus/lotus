import React, { FC } from "react";
import { Card, Divider, DatePicker } from "antd";
import RevenueDisplay from "./RevenueDisplay";
import SubscriptionStatistics from "./SubscriptionStatistics";
import MetricBarGraph from "./MetricBarGraph";
import moment from "moment";

const { RangePicker } = DatePicker;
const dateFormat = "YYYY/MM/DD";
const defaultDate = [moment().subtract(1, "months"), moment()];

const Dashboard: FC = () => {
  const [dateRange, setDateRange] = React.useState<any>([
    moment().subtract(1, "months"),
    moment(),
  ]);

  return (
    <div>
      <div className="flex flex-row items-center">
        <h1 className="text-3xl font-main mb-10">Dashboard</h1>
        <div className="items-center ml-auto">
          <RangePicker
            bordered={false}
            format={dateFormat}
            defaultValue={[moment().subtract(1, "months"), moment()]}
            onCalendarChange={(dates) => {
              setDateRange(dates);
            }}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 justify-center ">
        <Card className="max-w-lg">
          <RevenueDisplay />
        </Card>
        <Card className="max-w-lg">
          <SubscriptionStatistics />
        </Card>
      </div>
      <Divider />
      <div className="my-10">
        <MetricBarGraph />
      </div>
    </div>
  );
};

export default Dashboard;
