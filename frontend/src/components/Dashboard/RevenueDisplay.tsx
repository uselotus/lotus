import React, { useEffect, useState } from "react";
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

const displayMetric = (metric: number | undefined): number => {
  if (metric === undefined) {
    return 0;
  }
  return metric;
};

function RevenueDisplay(props: {
  total_revenue_1: number | undefined;
  total_revenue_2: number | undefined;
  earned_revenue_1: number | undefined;
  earned_revenue_2: number | undefined;
  isLoading: boolean;
}) {
  const [percentageChange, setPercentageChange] = useState<number>(0);

  useEffect(() => {
    setPercentageChange(
      computePercentageChange(props.earned_revenue_1, props.earned_revenue_2)
    );
  }, [props.earned_revenue_1, props.earned_revenue_2]);
  return (
    <Paper color="white" border={true}>
      <div className="grid grid-flow-col auto-cols-auto	 justify-between">
        <div>
          <p className="text-base mb-4">Earned Revenue</p>
          {props.isLoading ? (
            <LoadingSpinner />
          ) : (
            <span className="text-3xl font-bold">
              {new Intl.NumberFormat("en-US", {
                style: "currency",
                currency: "USD",
              }).format(displayMetric(props.earned_revenue_1))}
            </span>
          )}

          <span></span>
        </div>

        <div>
          <p className="text-base mb-4">Previous Period</p>
          {percentageChange >= 0 ? (
            <span className="text-[#34B220] text-3xl">
              +{percentageChange.toFixed(2)}%{" "}
            </span>
          ) : (
            <span className="text-[#cf1322] text-3xl">
              {percentageChange.toFixed(0)}%{" "}
            </span>
          )}
        </div>
      </div>
    </Paper>
  );
}

export default RevenueDisplay;
