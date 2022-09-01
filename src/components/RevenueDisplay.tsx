import React, { useEffect, useState } from "react";
import { RevenueType } from "../types/revenue-type";
import { GetRevenue } from "../api/api";
import { Statistic, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

function RevenueDisplay() {
  const defaultData = {
    revenue: "34,234",
    start_month: "Jan 2022",
    end_month: "Feb 2022",
    percent_change: 0.234,
  };
  const [revenueData, setRevenueData] = useState<RevenueType>(defaultData);

  //   useEffect(() => {
  //     GetRevenue.getMonthlyRevenue().then((data) => {
  //       if (data) {
  //         setRevenueData(data);
  //       }
  //     });
  //   }, []);
  return (
    <div className="px-2 py-2">
      <h1 className="text-xl font-main font-bold mb-4">Monthly Revenue</h1>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <h2 className="text-3xl">$ {revenueData.revenue}</h2>
        <div>
          {revenueData.percent_change >= 0 ? (
            <Statistic
              value={revenueData.percent_change}
              valueStyle={{
                color: "#3f8600",
                fontSize: "1.875rem",
                lineHeight: "2.25rem",
              }}
              precision={2}
              prefix={<ArrowUpOutlined />}
              suffix="%"
              className="text-3xl"
            />
          ) : (
            <Statistic
              value={revenueData.percent_change}
              valueStyle={{
                color: "#cf1322",
                fontSize: "1.875rem",
                lineHeight: "2.25rem",
              }}
              precision={2}
              prefix={<ArrowDownOutlined />}
              suffix="%"
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default RevenueDisplay;
