import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";
import { RevenuePeriod } from "../../types/revenue-type";
import LoadingSpinner from "../LoadingSpinner";

const defaultData = [
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

function RevenueBarGraph(props: {
  data?: RevenuePeriod[];
  isLoading: boolean;
}) {
  const [data, setData] = useState<any>(defaultData);
  const config = {
    data,
    isStack: true,
    xField: "day",
    yField: "revenue",
    seriesField: "type",
    isRange: true,
    maxColumnWidth: 30,
    color: ["#DEC27D", "#72A5FD", "#DEC27D"],
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
  // if (props.isLoading || props.data === undefined) {
  //   return (
  //     <div>
  //       <LoadingSpinner />
  //     </div>
  //   );
  // }
  return (
    <div>
      <Column {...config} />
    </div>
  );
}

export default RevenueBarGraph;
