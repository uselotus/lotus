import React, { FC } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Line, Pie } from "@ant-design/plots";
import { Select, Typography } from "antd";
// import { Card, ColGrid, Metric, Text } from "@tremor/react";

import { useQuery, UseQueryResult } from "react-query";
import { Backtests } from "../api/api";
import { BacktestResultType } from "../types/experiment-type";
import { PageLayout } from "../components/base/PageLayout";

const { Option } = Select;

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
    <PageLayout title="Experiment Results">
      <div>
        {isError && <div>Something went wrong</div>}
        <div className=" border-2 border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7">
          <div className="grid grid-cols-2 gap-5">
            <div className=" mb-10">
              <h2 className="font-bold">experiment 23423</h2>
            </div>
            <h3>Date Run: </h3>

            <div className=" col-span-1">
              <h3 className=" font-bold">
                2002-23-23 - 2002-23-12
                {/* {experiment.start_time} - {experiment.end_time} */}
              </h3>
            </div>
            <div className="col-span-1">
              <h3 className=" font-bold">
                Status: {/* {experiment.status} */}
                {/* {experiment.start_time} - {experiment.end_time} */}
              </h3>
            </div>
            <div className="col-span-1">
              {/* <Card key={23}>
                <Text>dsf</Text>
                <Metric>234</Metric>
              </Card> */}
            </div>
          </div>
        </div>
        {experiment !== undefined && (
          <div>
            <div>
              <h3> Substitutions</h3>
              <Select defaultValue="lucy" style={{ width: 120 }}>
                {experiment.backtest_results.substitution_results.map(
                  (substitution) => (
                    <Option value={substitution.substitution_name}>
                      {substitution.substitution_name}
                    </Option>
                  )
                )}
              </Select>
            </div>
            <div>
              <Line {...cumulative_config} />
            </div>
          </div>
        )}

        {/* <Pie {...metric_config} /> */}
      </div>
    </PageLayout>
  );
};

export default ExperimentResults;
