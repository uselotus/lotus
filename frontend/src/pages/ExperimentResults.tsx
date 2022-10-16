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
import { BacktestResultType } from "../types/experiment-type";
import { PageLayout } from "../components/base/PageLayout";

const arrowURL = new URL("../components/arrow.svg", import.meta.url).href;

const { Option } = Select;

const fakeData = [
  { date: "2019-03", original_plan_revenue: 350, new_plan_revenue: 200 },
  { date: "2019-04", original_plan_revenue: 900, new_plan_revenue: 300 },
  { date: "2019-05", original_plan_revenue: 300, new_plan_revenue: 400 },
  { date: "2019-06", original_plan_revenue: 450, new_plan_revenue: 500 },
  { date: "2019-07", original_plan_revenue: 470, new_plan_revenue: 600 },
];

const fakeData2 = [
  {
    type: "Plan-1",
    value: 27,
  },
  {
    type: "Plan-2",
    value: 25,
  },
  {
    type: "Plan-3",
    value: 18,
  },
];

const fakecustomers = [
  {
    name: "Jim",
    amount: "1,365",
    share: "39%",
  },
  {
    name: "John",
    amount: "984",
    share: "20.1%",
  },
  {
    name: "Steve",
    amount: "1,365",
    share: "39%",
  },
  {
    name: "Johneson",
    amount: "789",
    share: "10.1%",
  },
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

  const dataFormatter = (number: number) => `$${number.toFixed(2)}`;

  const config = {
    legend: {
      position: "bottom" as any,
    },
    appendPadding: 20,
    data: fakeData2,
    angleField: "value",
    colorField: "type",
    radius: 1,
    innerRadius: 0.8,
    label: {
      type: "inner",
      offset: "-50%",
      content: "{value}%",
      style: {
        textAlign: "center",
        fontSize: 12,
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
        content: "",
        style: {
          whiteSpace: "pre-wrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        },
      },
    },
  };
  return (
    <PageLayout title="Results">
      <div>
        {!isError ? (
          <div>Something went wrong</div>
        ) : (
          <div className=" border-2 border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7">
            <div className="grid grid-cols-2 gap-5">
              <div className=" mb-3">
                <NewTitle>Experiment dsfads</NewTitle>
              </div>
              <h3 className="font-bold">Date Run: 2002-23-23</h3>

              <div className=" col-span-1 self-center">
                <h3 className=" font-bold">Date Range:</h3>
                <h3>
                  2002-23-23 to 2002-23-12
                  {/* {experiment.start_time} to {experiment.end_time} */}
                </h3>
              </div>
              <div className="col-span-1">
                <h3 className=" font-bold">
                  Status: Completed{/* {experiment.status} */}
                </h3>
              </div>
              <div className="grid grid-cols-auto">
                <h3 className=" font-bold">Total Revenue</h3>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-5">
              <div className="justify-self-center w-2/5 mt-6">
                <Card key={234}>
                  <div className="justify-center">
                    <Text>sdfds</Text>
                    <Metric>234</Metric>
                  </div>
                </Card>
              </div>
              <div className="justify-self-center self-center	">
                <img src={arrowURL} alt="arrow" className="mb-4" />
              </div>
              <div className=" justify-self-center w-2/5 mt-6">
                <Card key={23}>
                  <Text>dsf</Text>
                  <Metric>234</Metric>
                </Card>
              </div>
            </div>
          </div>
        )}

        {experiment !== undefined && (
          <div>
            <div>
              <h3> Substitutions</h3>
              <Select defaultValue="lucy" style={{ width: 120 }}>
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
          </div>
        )}
        <div className="border-2 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7 ">
          <h2>Revenue Over Time</h2>
          <LineChart
            data={fakeData}
            categories={["original_plan_revenue", "new_plan_revenue"]}
            dataKey=""
            colors={["gray"]}
            valueFormatter={dataFormatter}
            startEndOnly={false}
            showXAxis={true}
            showYAxis={true}
            yAxisWidth="w-14"
            showTooltip={true}
            showLegend={true}
            showGridLines={true}
            showAnimation={true}
            height="h-80"
            marginTop="mt-0"
          />
        </div>
        <div className="border-2 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7 ">
          <h2>Revenue By Metric</h2>
          <ColGrid numColsMd={2}>
            <div>
              <Title marginTop="mt-8">Old Plan</Title>
              <Pie {...config} />
            </div>
            <div>
              <Title marginTop="mt-8">New Plan</Title>
              <Pie {...config} />
            </div>
          </ColGrid>
        </div>

        <div className="border-2 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7 ">
          <h2>Top Customers</h2>

          <ColGrid numColsMd={4} gapX="gap-x-8" gapY="gap-y-2">
            <div>
              <Title marginTop="mt-8">Revenue on Plan</Title>
              <List marginTop="mt-2">
                {fakecustomers.map((item) => (
                  <ListItem key={item.name}>
                    <Text>{item.name}</Text>
                    <Text>
                      <Bold>{item.amount}</Bold>{" "}
                    </Text>
                  </ListItem>
                ))}
              </List>
            </div>
            <div>
              <Title marginTop="mt-8">Revenue on</Title>
              <List marginTop="mt-2">
                {fakecustomers.map((item) => (
                  <ListItem key={item.name}>
                    <Text>{item.name}</Text>
                    <Text>
                      <Bold>{item.amount}</Bold>{" "}
                    </Text>
                  </ListItem>
                ))}
              </List>
            </div>
            <div>
              <Title marginTop="mt-8">Top Revenue Increases</Title>
              <List marginTop="mt-2">
                {fakecustomers.map((item) => (
                  <ListItem key={item.name}>
                    <Text>{item.name}</Text>
                    <Text>
                      <Bold>{item.amount}</Bold>{" "}
                    </Text>
                  </ListItem>
                ))}
              </List>
            </div>
            <div>
              <Title marginTop="mt-8">Top Revenue Decreases</Title>
              <List marginTop="mt-2">
                {fakecustomers.map((item) => (
                  <ListItem key={item.name}>
                    <Text>{item.name}</Text>
                    <Text>
                      <Bold>{item.amount}</Bold>{" "}
                    </Text>
                  </ListItem>
                ))}
              </List>
            </div>
          </ColGrid>
        </div>

        {/* <Pie {...metric_config} /> */}
      </div>
    </PageLayout>
  );
};

export default ExperimentResults;
