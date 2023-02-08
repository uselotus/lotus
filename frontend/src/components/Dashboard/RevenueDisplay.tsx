/* eslint-disable camelcase */
import React, { Fragment, useEffect, useState } from "react";
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

function RevenueDisplay({
  earned_revenue_1,
  earned_revenue_2,
  isLoading,
}: {
  earned_revenue_1: number | undefined;
  earned_revenue_2: number | undefined;
  isLoading: boolean;
}) {
  const [percentageChange, setPercentageChange] = useState<number>(0);

  useEffect(() => {
    setPercentageChange(
      computePercentageChange(earned_revenue_1, earned_revenue_2)
    );
  }, [earned_revenue_1, earned_revenue_2]);
  return (
    <Paper color="white" border>
      <div className="grid grid-flow-col auto-cols-auto  justify-between">
        <div>
          <p className="text-sm mb-4 leading-[18px] font-normal">
            Earned Revenue
          </p>
          {isLoading ? (
            <div className="flex justify-center">
              <LoadingSpinner />
            </div>
          ) : (
            <>
              <span className="text-2xl font-bold mb-4">
                {new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                }).format(displayMetric(earned_revenue_1))}
              </span>
              <p className="text-sm mb-4 mt-4 leading-[18px] font-normal">
                Prev. Period{" "}
                {percentageChange >= 0 ? (
                  <span className="text-[#34B220] ">
                    +{percentageChange.toFixed(2)}%{" "}
                  </span>
                ) : (
                  <span className="text-[#cf1322] ">
                    {percentageChange.toFixed(0)}%{" "}
                  </span>
                )}
              </p>
            </>
          )}
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
