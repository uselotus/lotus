import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";

const defaultData = [
  {
    day: "Jan 21",
    revenue: 3,
    type: "API 1",
  },
  {
    day: "Jan 21",
    revenue: 4,
    type: "API 2",
  },
  {
    day: "Jan 22",
    revenue: 6,
    type: "API 1",
  },
  {
    day: "Jan 22",
    revenue: 3,
    type: "API 2",
  },
  {
    day: "Jan 23",
    revenue: 6,
    type: "API 1",
  },
  {
    day: "Jan 23",
    revenue: 0,
    type: "API 2",
  },
];

function MetricBarGraph() {
  const [data, setData] = useState<any>(defaultData);
  const config = {
    data,
    isStack: true,
    xField: "day",
    yField: "revenue",
    seriesField: "type",
    isRange: true,
    maxColumnWidth: 30,
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
  return (
    <div className="">
      <Column {...config} />
    </div>
  );
}

export default MetricBarGraph;
