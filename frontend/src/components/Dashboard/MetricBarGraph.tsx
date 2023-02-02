import { Column } from "@ant-design/plots";
import React, { useState, useEffect } from "react";
import { Select } from "antd";
import { useQuery, UseQueryResult } from "react-query";
import LoadingSpinner from "../LoadingSpinner";
import { MetricUsage } from "../../types/metric-type";
import { Metrics } from "../../api/api";
import { Paper } from "../base/Paper";

const { Option } = Select;

interface ChartDataType {
  date: string;
  metric_amount: number | any;
  type: string;
}

// Generate more defaultData for the month of august

function MetricBarGraph(props: { range: any }) {
  const [selectedMetric, setSelectedMetric] = useState<string>();
  const [metricList, setMetricList] = useState<string[]>([]);
  const [chartData, setChartData] = useState<ChartDataType[]>([]);

  const { data, isLoading }: UseQueryResult<MetricUsage> =
    useQuery<MetricUsage>(["dashboard_metric_graph", props.range], () =>
      Metrics.getMetricUsage(
        props.range[0].format("YYYY-MM-DD"),
        props.range[1].format("YYYY-MM-DD"),
        10
      ).then((res) => res)
    );
  const changeMetric = (value: string) => {
    const compressedArray: ChartDataType[] = [];
    setSelectedMetric(value);

    if (data?.metrics && Object.keys(data.metrics).length > 0) {
      const daily_data = data?.metrics[value].data;

      for (let i = 0; i < daily_data.length; i++) {
        const {date} = daily_data[i];
        for (const k in daily_data[i].customer_usages) {
          compressedArray.push({
            date,
            metric_amount: daily_data[i].customer_usages[k],
            type: k,
          });
        }
      }
    }
    setChartData(compressedArray);
  };
  useEffect(() => {
    if (data?.metrics && Object.keys(data.metrics).length > 0) {
      setMetricList(Object.keys(data.metrics));
      setSelectedMetric(Object.keys(data.metrics)[0]);
      changeMetric(Object.keys(data.metrics)[0]);
    } else {
      setMetricList([]);
      setSelectedMetric(undefined);
      changeMetric("");
    }
  }, [data]);

  const config = {
    data: chartData,
    isStack: true,
    xField: "date",
    yField: "metric_amount",
    seriesField: "type",
    isRange: true,
    maxColumnWidth: 30,

    legend: {
      position: "bottom-left",
    },

    color: ["#33658A", "#547AA5", "#C3986B", "#D9D9D9", "#171412"],
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
        <h3>No Usage Data</h3>
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <Paper border>
      <div className="flex flex-row items-center mb-12 space-x-4 justify-between">
        <h2>Metric Usage</h2>
        <Select
          defaultValue="Select Metric"
          onChange={changeMetric}
          value={selectedMetric}
          className="w-4/12 self-center"
        >
          {metricList.map((metric_name) => (
            <Option value={metric_name} loading={isLoading}>
              {metric_name}
            </Option>
          ))}
        </Select>
      </div>

      <div className="mt-6">
        <Column {...config} />
      </div>
    </Paper>
  );
}

export default MetricBarGraph;
