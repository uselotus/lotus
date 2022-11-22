import React, { FC, useEffect } from "react";
import { Column } from "@ant-design/plots";
import { Select } from "antd";
import dayjs from "dayjs";

const CustomerInfoView: FC<any> = ({ data, cost_data, onDateChange }) => {
  const [transformedGraphData, setTransformedGraphData] = React.useState<any>(
    []
  );

  useEffect(() => {
    const newgraphdata = cost_data.per_day.map((day: any) => {
      var result_list = day.cost_data.map((metric: any) => {
        return {
          date: day.date,
          amount: metric.cost,
          metric: metric.metric.billable_metric_name,
          type: "cost",
        };
      });

      result_list.push({
        date: day.date,
        amount: day.revenue,
        type: "revenue",
        metric: "Revenue",
      });
      return result_list;
    });
    setTransformedGraphData(newgraphdata.flat(1));
  }, [cost_data]);

  const onSwitch = (key: string) => {
    var start_date;
    var end_date = dayjs().format("YYYY-MM-DD");

    switch (key) {
      case "1":
        start_date = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        break;
      case "2":
        start_date = dayjs().subtract(2, "month").format("YYYY-MM-DD");
        break;
      case "3":
        start_date = dayjs().startOf("month").format("YYYY-MM-DD");
        break;
      case "4":
        start_date = dayjs().startOf("year").format("YYYY-MM-DD");
        break;
    }
    console.log(start_date);

    onDateChange(start_date, end_date);
  };

  const config = {
    data: transformedGraphData,
    xField: "date",
    yField: "amount",
    isGroup: true,
    isStack: true,
    seriesField: "metric",
    groupField: "type",
  };

  return (
    <div className="grid">
      <div className="flex flex-col mb-8">
        <div>
          <h2 className="mb-2 pb-4 pt-4 font-bold text-main">
            Customer Details
          </h2>
        </div>
        <div className="customer-detail-card">
          <p>
            <b>Customer Name:</b> {data.customer_name}
          </p>
          <p>
            <b>Customer ID:</b> {data.customer_id ?? "N/A"}
          </p>
          <p>
            <b>Email:</b> {data.email ?? "N/A"}
          </p>
          <p>
            <b>Billing Address:</b> {data.billing_address ?? "N/A"}
          </p>
          <p>
            <b>Amount Due On Next Invoice:</b> {"$"}
            {data.total_amount_due}
          </p>
        </div>
      </div>
      <div className="space-y-4">
        <div className="flex items-center space-x-8">
          <h2 className="mb-2 pb-4 pt-4 font-bold text-main">
            Revenue vs Cost Analysis
          </h2>
          <div className="justify-self-end">
            {" "}
            Date Range :{"   "}
            <Select defaultValue={"1"} onChange={onSwitch}>
              <Select.Option value="1">Last 30 Days</Select.Option>
              <Select.Option value="2">Last 60 Days</Select.Option>
              <Select.Option value="3">This Month</Select.Option>
              <Select.Option value="4">Year to date</Select.Option>
            </Select>
          </div>
        </div>
        <Column {...config} />
      </div>
    </div>
  );
};

export default CustomerInfoView;
