import React, { useEffect, useState } from "react";
import { RevenueType } from "../../types/revenue-type";
import { GetRevenue } from "../../api/api";
import { Statistic, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { useQuery, UseQueryResult } from "react-query";
import LoadingSpinner from "../LoadingSpinner";
import { Paper } from "../base/Paper";

const computePercentageChange = (
  current: number | undefined,
  previous: number | undefined
): number => {
  if (previous === 0 || current === undefined || previous === undefined) {
    return 0;
  }
  return ((current - previous) / previous) * 100;
};

function RevenueDisplay(props: {
  total_revenue_1: number | undefined;
  total_revenue_2: number | undefined;
  isLoading: boolean;
}) {
  const [percentageChange, setPercentageChange] = useState<number>(0);
  useEffect(() => {
    setPercentageChange(
      computePercentageChange(props.total_revenue_1, props.total_revenue_2)
    );
  }, [props.total_revenue_1, props.total_revenue_2]);
  if (
    props.isLoading ||
    props.total_revenue_1 === undefined ||
    props.total_revenue_2 === undefined
  ) {
    return (
      <div>
        <LoadingSpinner />
      </div>
    );
  }
  return (
    <Paper>
      <h1 className="text-base font-normal mb-4">Total Revenue</h1>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <span className="text-3xl font-bold">
          {new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
          }).format(props.total_revenue_1)}
        </span>
        <div>
          {percentageChange >= 0 ? (
            <span className="text-[#34B220] text-3xl">
              +{percentageChange.toFixed(2)}%{" "}
            </span>
          ) : (
            <span className="text-[#cf1322] text-3xl">
              -{percentageChange.toFixed(0)}%{" "}
            </span>
          )}
          <span>Previous-period</span>
        </div>
      </div>
    </Paper>
  );
}

export default RevenueDisplay;
