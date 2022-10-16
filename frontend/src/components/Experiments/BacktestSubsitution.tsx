import React, { FC, useEffect } from "react";
import { BacktestType, SpecificResults } from "../../types/experiment-type";
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
import { Title as NewTitle } from "../base/Typograpy/index.";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
const arrowURL = new URL("../arrow.svg", import.meta.url).href;

interface Props {
  substitution: SpecificResults;
}

const BacktestSubstitution: FC<Props> = ({ substitution }) => {
  const dataFormatter = (number: number) => `$${number.toFixed(2)}`;
  const [revenueLineGraph, setRevenueLineGraph] = React.useState<any>([]);
  const categories = [
    substitution.original_plan.plan_name,
    "[new]" + substitution.new_plan.plan_name,
  ];

  const pieConfigNew = {
    legend: {
      position: "bottom" as any,
    },
    appendPadding: 20,
    data: substitution.results.revenue_by_metric,
    angleField: "original_plan_revenue",
    colorField: "metric_name",
    radius: 1,
    innerRadius: 0.8,
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
        content: "",
        style: {
          whiteSpace: "pre-wrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        },
      },
    },
  };

  const pieConfigOld = {
    legend: {
      position: "bottom" as any,
    },
    appendPadding: 20,
    data: substitution.results.revenue_by_metric,
    angleField: "new_plan_revenue",
    colorField: "metric_name",
    radius: 1,
    innerRadius: 0.8,
    label: {
      type: "inner",
      offset: "-50%",
      content: "{value}",
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

  useEffect(() => {
    if (substitution.results.cumulative_revenue !== undefined) {
      const newRevLineGraph = substitution.results.cumulative_revenue;
      for (let i = 0; i < newRevLineGraph.length; i++) {
        newRevLineGraph[i][categories[0]] =
          newRevLineGraph[i]["original_plan_revenue"];
        console.log(newRevLineGraph);
        newRevLineGraph[i][categories[1]] =
          newRevLineGraph[i]["new_plan_revenue"];
      }

      console.log(newRevLineGraph);
      setRevenueLineGraph(newRevLineGraph);
    }
  }, [substitution.results.cumulative_revenue]);

  return (
    <div>
      <div className="grid grid-cols-3 gap-5">
        <div className="justify-self-center w-2/5 mt-6">
          <Card key={234}>
            <div className="justify-center">
              <Text>{substitution.original_plan.plan_name}</Text>
              <Metric>
                {dataFormatter(substitution.original_plan.plan_revenue)}
              </Metric>
            </div>
          </Card>
        </div>
        <div className="justify-self-center self-center	">
          <img src={arrowURL} alt="arrow" className="mb-4" />
        </div>
        <div className=" justify-self-center w-2/5 mt-6">
          <Card key={23}>
            <Text>{substitution.new_plan.plan_name}</Text>
            <Metric>{dataFormatter(substitution.new_plan.plan_revenue)}</Metric>
          </Card>
        </div>
      </div>
      <div className="border-2 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7 ">
        <h2>Revenue Over Time</h2>
        <LineChart
          data={revenueLineGraph}
          categories={categories}
          dataKey="date"
          colors={["gray", "amber"]}
          valueFormatter={dataFormatter}
          startEndOnly={false}
          showXAxis={true}
          showYAxis={true}
          yAxisWidth="w-20"
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
            <Pie {...pieConfigOld} />
          </div>
          <div>
            <Title marginTop="mt-8">New Plan</Title>
            <Pie {...pieConfigNew} />
          </div>
        </ColGrid>
      </div>

      <div className="border-2 bg-[#F7F8FD] px-4 py-5 sm:px-6 my-7 ">
        <h2>Top Customers</h2>

        <ColGrid numColsMd={4} gapX="gap-x-8" gapY="gap-y-2">
          <div>
            <Title marginTop="mt-8">Revenue on Original</Title>
            <List marginTop="mt-2">
              {substitution.results.top_customers.original_plan_revenue.map(
                (item) => (
                  <ListItem key={item.customer_id}>
                    <Text>{item.customer_name}</Text>
                    <Text>
                      <Bold>{dataFormatter(item.value)}</Bold>{" "}
                    </Text>
                  </ListItem>
                )
              )}
            </List>
          </div>
          <div>
            <Title marginTop="mt-8">Revenue on New</Title>
            <List marginTop="mt-2">
              {substitution.results.top_customers.new_plan_revenue.map(
                (item) => (
                  <ListItem key={item.customer_id}>
                    <Text>{item.customer_name}</Text>
                    <Text>
                      <Bold>{dataFormatter(item.value)}</Bold>{" "}
                    </Text>
                  </ListItem>
                )
              )}
            </List>
          </div>
          <div>
            <Title marginTop="mt-8">Top Revenue Increases</Title>
            <List marginTop="mt-2">
              {substitution.results.top_customers.biggest_pct_increase.map(
                (item) => (
                  <ListItem key={item.customer_id}>
                    <Text>{item.customer_name}</Text>
                    <Text>
                      <Bold>{item.value.toFixed(2)}</Bold>{" "}
                    </Text>
                  </ListItem>
                )
              )}
            </List>
          </div>
          <div>
            <Title marginTop="mt-8">Top Revenue Decreases</Title>
            <List marginTop="mt-2">
              {substitution.results.top_customers.biggest_pct_decrease.map(
                (item) => (
                  <ListItem key={item.customer_id}>
                    <Text>{item.customer_name}</Text>
                    <Text>
                      <Bold>{item.value.toFixed(2)}</Bold>{" "}
                    </Text>
                  </ListItem>
                )
              )}
            </List>
          </div>
        </ColGrid>
      </div>
    </div>
  );
};

export default BacktestSubstitution;
