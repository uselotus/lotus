import React, { FC } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Line, Pie } from "@ant-design/plots";

import { useQuery, UseQueryResult } from "react-query";
import { Backtests } from "../api/api";
import { BacktestResultType } from "../types/experiment-type";

const fakeData = [
  { date: "2019-03", value: 350 },
  { date: "2019-04", value: 900 },
  { date: "2019-05", value: 300 },
  { date: "2019-06", value: 450 },
  { date: "2019-07", value: 470 },
];

const ExperimentResults: FC = () => {
  const navigate = useNavigate();
  const params = useParams();
  const { experimentId } = params as any;

  const {
    data: experiment,
    isLoading,
    isError,
  }: UseQueryResult<BacktestResultType> = useQuery<BacktestResultType>(
    ["experiment_results", experimentId],
    () =>
      Backtests.getBacktestResults(experimentId).then(
        (res: BacktestResultType) => {
          return res;
        }
      )
  );
  const cumulative_config = {
    fakeData,
    xField: "date",
    yField: "value",
    seriesField: "category",
    xAxis: {
      type: "time",
    },
    yAxis: {
      label: {
        formatter: (v) =>
          `${v}`.replace(/\d{1,3}(?=(\d{3})+$)/g, (s) => `${s},`),
      },
    },
  };
  const metric_config = {
    appendPadding: 10,
    fakeData,
    angleField: "value",
    colorField: "type",
    radius: 1,
    innerRadius: 0.6,
    label: {
      type: "inner",
      offset: "-50%",
      content: "{value}",
      style: {
        textAlign: "center",
        fontSize: 14,
      },
    },
    interactions: [
      {
        type: "element-selected",
      },
      {
        type: "element-active",
      },
    ],
    statistic: {
      title: false,
      content: {
        style: {
          whiteSpace: "pre-wrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        },
      },
    },
  };

  return (
    <div>
      {isError && <div>Something went wrong</div>}
      <div className=" border-2 border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6">
        <h3 className=" font-bold">Experiment Results</h3>
        <div className="grid grid-cols-2">
          <div className="col-span-1">
            <h3 className=" font-bold">
              {experiment.start_time} - {experiment.end_time}
            </h3>
          </div>
        </div>
      </div>
      <Line {...cumulative_config} />
      <Pie {...metric_config} />
    </div>
  );
};

export default ExperimentResults;
