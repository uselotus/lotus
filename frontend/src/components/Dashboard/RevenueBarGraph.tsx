import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";
import { RevenuePeriod } from "../../types/revenue-type";
import { Paper } from "../base/Paper";
import LoadingSpinner from "../LoadingSpinner";

interface RevenueChartData {
  day: string;
  revenue: number;
  type: string | any;
}

//Generate more defaultData for the month of august

function RevenueBarGraph(props: {
  data?: RevenuePeriod[];
  isLoading: boolean;
}) {
  const [data, setData] = useState<RevenueChartData[]>([]);

  useEffect(() => {
    if (props.data) {
      const compressedArray: RevenueChartData[] = [];
      for (let i = 0; i < props.data.length; i++) {
        const metric = props.data[i].metric;
        for (const k in props.data[i].data) {
          compressedArray.push({
            day: props.data[i].data[k].date,
            revenue: props.data[i].data[k].metric_revenue,
            type: metric,
          });
        }
      }
      setData(compressedArray);
    }
  }, [props.data]);

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
  if (props.isLoading || props.data === undefined) {
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
