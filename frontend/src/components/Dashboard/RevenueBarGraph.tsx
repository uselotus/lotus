/* eslint-disable react/jsx-props-no-spreading */
/* eslint-disable no-plusplus */
import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";
import { RevenuePeriod } from "../../types/revenue-type";
import { Paper } from "../base/Paper";
import LoadingSpinner from "../LoadingSpinner";

interface RevenueChartData {
  day: string;
  revenue: number;
  type: string;
}

// Generate more defaultData for the month of august

function RevenueBarGraph({
  data: propsData,
  isLoading,
}: {
  data?: RevenuePeriod[];
  isLoading: boolean;
}) {
  const [data, setData] = useState<RevenueChartData[]>([]);

  useEffect(() => {
    if (propsData) {
      const compressedArray: RevenueChartData[] = [];
      for (let i = 0; i < propsData.length; i++) {
        const { metric } = propsData[i];
        // eslint-disable-next-line no-restricted-syntax, guard-for-in
        for (const k in propsData[i].data) {
          compressedArray.push({
            day: propsData[i].data[k].date,
            revenue: propsData[i].data[k].metric_revenue,
            type: metric,
          });
        }
      }
      setData(compressedArray);
    }
  }, [propsData]);

  const config = {
    data,
    isStack: true,
    xField: "day",
    yField: "revenue",
    seriesField: "type",
    isRange: true,
    maxColumnWidth: 30,

    // color: ["1d4427", "245530", "2f6e3b", "55b467", "e5fbeb"],
    label: {
      layout: [
        {
          type: "interval-adjust-position",
        },
        {
          type: "interval-hide-overlap",
        },
        {
          type: "adjust-color",
        },
      ],
    },
  };
  if (isLoading || propsData === undefined) {
    return (
      <Paper>
        <h3>No Revenue Data</h3>
        <LoadingSpinner />
      </Paper>
    );
  }
  return (
    <Paper>
      <h2 className="mb-5">Revenue Accrued</h2>
      <Column {...config} />
    </Paper>
  );
}

export default RevenueBarGraph;
