import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";

const defaultData = [
  {
    day: "Aug 21",
    revenue: 3,
    type: "API 1",
  },
  {
    day: "Aug 21",
    revenue: 4,
    type: "API 2",
  },
  {
    day: "Aug 22",
    revenue: 6,
    type: "API 1",
  },
  {
    day: "Aug 22",
    revenue: 3,
    type: "API 2",
  },
  {
    day: "Aug 23",
    revenue: 24,
    type: "API 1",
  },
  {
    day: "Aug 23",
    revenue: 3,
    type: "API 2",
  },
  {
    day: "Aug 24",
    revenue: 53,
    type: "API 1",
  },
  {
    day: "Aug 24",
    revenue: 2,
    type: "API 2",
  },
  {
    day: "Aug 26",
    revenue: 23,
    type: "API 1",
  },
  {
    day: "Aug 26",
    revenue: 6,
    type: "API 2",
  },
  {
    day: "Aug 27",
    revenue: 20,
    type: "API 1",
  },
  {
    day: "Aug 27",
    revenue: 10,
    type: "API 2",
  },
  //generate more data
  {
    day: "Aug 28",
    revenue: 6,
    type: "API 1",
  },
  {
    day: "Aug 28",
    revenue: 4,
    type: "API 2",
  },
];

//Generate more defaultData for the month of august

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
    colorField: "type", // or seriesField in some cases
    color: ["#DEC27D", "#72A5FD", "#DEC27D"],
    padding: "auto",
    legend: {
      layout: "vertical",
      position: "left",
    },
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
