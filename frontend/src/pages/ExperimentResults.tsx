import React, { FC } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Select, Typography } from "antd";
import {
  Card,
  ColGrid,
  Metric,
  Text,
  LineChart,
  Title,
  Bold,
  List,
  ListItem,
  Tab,
  TabList,
} from "@tremor/react";
import { Pie } from "@ant-design/plots";
import { Title as NewTitle } from "../components/base/Typograpy/index.";

import { useQuery, UseQueryResult } from "react-query";
import { Backtests } from "../api/api";
import { BacktestResultType, SpecificResults } from "../types/experiment-type";
import { PageLayout } from "../components/base/PageLayout";
import BacktestSubstitution from "../components/Experiments/BacktestSubsitution";
import dayjs from "dayjs";

const arrowURL = new URL("../components/arrow.svg", import.meta.url).href;

const { Option } = Select;

const fakeData = [
  { date: "2019-03", original_plan_revenue: 350, new_plan_revenue: 200 },
  { date: "2019-04", original_plan_revenue: 900, new_plan_revenue: 300 },
  { date: "2019-05", original_plan_revenue: 300, new_plan_revenue: 400 },
  { date: "2019-06", original_plan_revenue: 450, new_plan_revenue: 500 },
  { date: "2019-07", original_plan_revenue: 470, new_plan_revenue: 600 },
];

const ExperimentResults: FC = () => {
  const navigate = useNavigate();
  const params = useParams();
  const { experimentId } = params as any;
  const [selectedSubstitution, setSelectedSubstitution] = React.useState<
    SpecificResults | undefined
  >();

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

  const changeSubstitution = (value: string) => {
    const selectedSubstitution =
      experiment?.backtest_results.substitution_results.find(
        (substitution) => substitution.substitution_name === value
      );
    setSelectedSubstitution(selectedSubstitution);
  };

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

  const dataFormatter = (number: number) => `$${number.toFixed(2)}`;
  return (
    <PageLayout title="Results">
      {isError || experiment === undefined ? (
        <div>Something went wrong</div>
      ) : (
        <div>
          <div className=" border-2 border-gray-200 bg-[#FAFAFA] px-4 py-5 sm:px-6 my-7">
            <div className="grid grid-cols-2 gap-5">
              <div className=" mb-3">
                <NewTitle>{experiment?.backtest_name}</NewTitle>
              </div>
              <h3 className="font-bold">
                Date Run: {dayjs(experiment.time_created).format("YYYY-MM-DD")}
              </h3>

              <div className=" col-span-1 self-center">
                <h3 className=" font-bold">Date Range:</h3>
                <h3 className="font-bold">
                  {experiment.start_date} to {experiment.end_date}
                </h3>
              </div>
              <div className="col-span-1">
                <h3 className=" font-bold">Status: {experiment.status}</h3>
              </div>
              <div className="grid grid-cols-auto">
                <h3 className=" font-bold">Total Revenue</h3>
              </div>
            </div>
          </div>
          <div>
            <h2> Substitutions</h2>
            <Select
              defaultValue="Select a Substitution"
              onChange={changeSubstitution}
            >
              {experiment.backtest_results.substitution_results.map(
                (substitution) => (
                  <Option
                    key={substitution.substitution_name}
                    value={substitution.substitution_name}
                  >
                    {substitution.substitution_name}
                  </Option>
                )
              )}
            </Select>
          </div>
          {selectedSubstitution && (
            <BacktestSubstitution substitution={selectedSubstitution} />
          )}
        </div>
      )}
    </PageLayout>
  );
};

export default ExperimentResults;
