import React, { FC, useEffect } from "react";
import { Column } from "@ant-design/plots";
import { Select } from "antd";
import dayjs from "dayjs";

const CustomerInfoView: FC<any> = ({ data, graph, onSelect }) => {
  const transformedGraphData = graph.per_day.map((day: any) => {
    var result_list = day.metric.map((metric: any) => {
      return {
        date: day.date,
        amount: metric.cost,
        metric: metric.type,
        type: metric.type,
      };
    });

    const onSwitch = (key: string) => {
      var start_date;
      var end_date = dayjs().format("YYYY-MM-DD");

      switch (key) {
        case "1":
          start_date = dayjs().subtract(1, "month").format("YYYY-MM-DD");
          break;
        case "2":
          start_date = dayjs().subtract(3, "month").format("YYYY-MM-DD");
          break;
        case "3":
          start_date = dayjs().startOf("month");
        case "4":
          start_date = dayjs().startOf("year");
      }

      onSelect(start_date, end_date);
    };

    result_list.push({
      date: day.date,
      amount: day.revenue,
      type: "revenue",
    });
    return result_list;
  });

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
    <div className="grid grid-rows-2">
      <div className="flex flex-col items-center justify-center">
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
            <b>Customer ID:</b> {data.customer_id}
          </p>
          <p>
            <b>Email:</b> {data.email}
          </p>
          <p>
            <b>Billing Address:</b> {data.billing_address}
          </p>
        </div>
      </div>
      <div className="space-y-4">
        <div>
          Date Range:
          <Select defaultValue={"1"}>
            <Select.Option value="1">Last 30 Days</Select.Option>
            <Select.Option value="2">Last 60 Days</Select.Option>
            <Select.Option value="3">This Month</Select.Option>
            <Select.Option value="4">Year to date</Select.Option>
          </Select>
        </div>
        <Column {...config} />
      </div>
    </div>
  );
};

export default CustomerInfoView;
