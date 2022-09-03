import React, { useEffect, useState } from "react";
import { RevenueType } from "../types/revenue-type";
import { GetRevenue } from "../api/api";
import { Statistic, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { useQuery } from "react-query";

function RevenueDisplay() {
  const { data, isLoading } = useQuery<RevenueType | Error>(
    ["total_revenue"],
    () =>
      GetRevenue.getMonthlyRevenue(
        "2022/12/02",
        "2022/12/02",
        "2022/12/02",
        "2022/12/02"
      ).then((res) => {
        return res;
      })
  );

  if (isLoading) {
    return <div>Loading...</div>;
  }
  return (
    <div className="px-2 py-2">
      <h1 className="text-xl font-main mb-4">Monthly Revenue</h1>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <h2 className="text-3xl">$ {3}</h2>
        <div>
          {3 >= 0 ? (
            <Statistic
              value={3}
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
              value={3}
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
