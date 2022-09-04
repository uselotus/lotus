import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";
import { RevenuePeriod } from "../../types/revenue-type";
import LoadingSpinner from "../LoadingSpinner";
import { Select } from "antd";
import { useQuery, UseQueryResult } from "react-query";
import { MetricUsage } from "../../types/metric-type";
import { Metrics } from "../../api/api";

const { Option } = Select;

interface ChartDataType {
  date: string;
  metric_amount: number;
  customer: string;
}

//Generate more defaultData for the month of august

function MetricBarGraph(props: { range: any }) {
  const [dateRange, setDateRange] = useState(props.range);

  const [selectedMetric, setSelectedMetric] = useState();
  const [metricList, setMetricList] = useState<string[]>([]);
  const [chartData, setChartData] = useState<ChartDataType[]>([]);

  const { data, isLoading }: UseQueryResult<MetricUsage> =
    useQuery<MetricUsage>(
      ["dashboard_metric_graph"],
      () =>
        Metrics.getmetricusage(
          dateRange[0].format("YYYY-MM-DD"),
          dateRange[1].format("YYYY-MM-DD")
        ).then((res) => {
          return res;
        }),
      { select: (data) => data }
    );

  useEffect(() => {
    if (data) {
      console.log(data);
      setMetricList(Object.keys(data));
    }
  }, [data]);

  const config = {
    data: chartData,
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
  if (isLoading || data === undefined) {
    return (
      <div>
        <LoadingSpinner />
      </div>
    );
  }

  const changeMetric = (value: string) => {
    let compressedArray: ChartDataType[] = [];

    const daily_data = data[value].data;
    for (let i = 0; i < daily_data.length; i++) {
      const date = daily_data[i].date;

      for (let j = 0; j < daily_data[i].customer_usages.length; j++) {
        compressedArray.push({
          date: date,
          metric_amount: daily_data[i].customer_usages[j].metric_amount,
          customer: daily_data[i].customer_usages[j].customer.name,
        });
      }
    }
    setChartData(compressedArray);
  };

  return (
    <div>
      <Select defaultValue="Select Metric" onChange={changeMetric}>
        {metricList.map((metric_name) => (
          <Option value={metric_name} loading={isLoading}>
            {metric_name}
          </Option>
        ))}
      </Select>
      <div>
        <Column {...config} />
      </div>
    </div>
  );
}

export default MetricBarGraph;
