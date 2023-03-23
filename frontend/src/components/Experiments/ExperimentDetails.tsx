import React, { FC, useEffect } from "react";
import {
  ColGrid,
  Text,
  LineChart,
  Bold,
  List,
  ListItem,
  Title,
} from "@tremor/react";
import { Pie } from "@ant-design/plots";
import { SpecificResults } from "../../types/experiment-type";
import { components } from "../../gen-types";

const arrowURL = new URL("../arrow.svg", import.meta.url).href;

interface Props {
  data: components["schemas"]["AnalysisResults"];
  kpi: string;
}

const ExperimentDetails: FC<Props> = ({ data, kpi }) => {
  const dataFormatter = (number: number) => `$${parseFloat(number).toFixed(2)}`;
  const dataFormatterNumber = (number: number) =>
    Math.round((number + Number.EPSILON) * 100) / 100;
  const [revenueLineGraph, setRevenueLineGraph] = React.useState<any>();
  const [revenuePerMetric, setRevenuePerMetric] = React.useState<{
    [planName: string]: { metric_name: string; revenue: number }[];
  }>();
  const [categories, setCategories] = React.useState<string[]>([]);

  function getPlanData(planName: string) {
    console.log(planName, 22);
    const matchingKey = Object.keys(revenuePerMetric).find(
      (key) => key === planName
    );
    console.log(planName);
    if (matchingKey !== undefined) {
      const matchingEntry = revenuePerMetric[matchingKey];
      console.log(matchingEntry, "matching");
      return matchingEntry;
    } else {
      console.log(`No entry found for plan ${planName}`);
    }
  }

  useEffect(() => {
    console.log(data);
    if (data && data.revenue_by_metric_graph !== undefined) {
      console.log(data.revenue_by_metric_graph, 23);
      let newPlans: string[] = [];
      for (let i = 0; i < data.revenue_by_metric_graph.length; i++) {
        newPlans.push(data.revenue_by_metric_graph[i].plan.plan_name);
      }
      setCategories(newPlans);
    }

    if (data && data.revenue_per_day_graph !== undefined) {
      const revenueData = data.revenue_per_day_graph.map((entry) => {
        const obj = { date: entry.date };
        entry.revenue_per_plan.forEach((plan) => {
          obj[plan.plan.plan_name] = plan.revenue;
        });
        return obj;
      });
      console.log(revenueData);
      console.log(categories);
      setRevenueLineGraph(revenueData);
    }

    if (data && data.revenue_by_metric_graph) {
      const result: {
        [planName: string]: { metric_name: string; revenue: number }[];
      } = {};
      data.revenue_by_metric_graph.forEach((entry) => {
        const planName = entry.plan.plan_name;
        if (!(planName in result)) {
          result[planName] = [];
        }
        entry.by_metric.forEach((metric) => {
          result[planName].push({
            metric_name: metric.metric.metric_name,
            revenue: parseFloat(metric.revenue),
          });
        });
      });
      console.log(result, 24234342);
      setRevenuePerMetric(result);
    }
  }, [data]);

  const pieConfigNew = {
    appendPadding: 20,
    data: data.revenue_by_metric_graph,
    angleField: "new_plan_revenue",
    colorField: "metric_name",
    radius: 1,
    color: ["#33658A", "#547AA5", "#C3986B", "#D9D9D9", "#171412"],

    innerRadius: 0.5,
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

  return (
    <div>
      {revenueLineGraph !== undefined && (
        <div className="border-2 bg-[#F9F9F9] px-4 py-6 sm:px-6 my-6 ">
          <div className="text-xl text-black font-semiBold">
            Revenue over time
          </div>

          <LineChart
            data={revenueLineGraph}
            categories={categories}
            dataKey="date"
            colors={["amber", "yellow"]}
            valueFormatter={dataFormatter}
            showXAxis
            showYAxis
            yAxisWidth="w-20"
            showTooltip
            showLegend
            showAnimation
            height="h-80"
          />
        </div>
      )}

      {revenuePerMetric !== undefined && (
        <div className="border-2 bg-[#F9F9F9] px-4 py-6 sm:px-6 my-6 ">
          <div className="text-xl font-semiBold text-black">
            Revenue by metric
          </div>
          <div className="w-full h-[1.5px] my-8 bg-card-divider" />
          <div className=" flex flex-wrap gap-26 ">
            {data.revenue_by_metric_graph.map((item) => (
              <div className="flex-grow">
                <div className="text-xl  font-semiBold">
                  {item.plan.plan_name}
                </div>
                <Pie
                  data={getPlanData(item.plan.plan_name)}
                  colorField="metric_name"
                  angleField="revenue"
                  color={[
                    "#C3986B",
                    "#E4D5C5",
                    "#EAECF0",
                    "#065F46",
                    "#171412",
                  ]}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-2 bg-[#F9F9F9] px-4 py-6 sm:px-6 my-6 ">
        <div className="text-xl  font-semiBold text-black">Top Customers</div>
        <div className="w-full h-[1.5px] my-8 bg-card-divider" />

        {/* <ColGrid numColsMd={4} gapX="gap-x-8" gapY="gap-y-2">
          <div>
            <Title marginTop="">Revenue on Original</Title>
            <List marginTop="mt-2">
              {data.top_customers.top_customers_by_revenue.map((item) => (
                <ListItem key={item.customer.customer_id}>
                  <Text>{item.customer.customer_name}</Text>
                  <Text>
                    <Bold>{(parseFloat(item.value) * 100).toFixed(2)}</Bold>
                    {"% "}
                  </Text>
                </ListItem>
              ))}
            </List>
          </div>
          <div>
            <Title marginTop="mt-8">Revenue on New</Title>
            <List marginTop="mt-2">
              {data.top_customers.top_customers_by_revenue.map((item) => (
                <ListItem key={item.customer.customer_id}>
                  <Text>{item.customer.customer_name}</Text>
                  <Text>
                    <Bold>{(parseFloat(item.value) * 100).toFixed(2)}</Bold>
                    {"% "}
                  </Text>
                </ListItem>
              ))}
            </List>
          </div>
          <div>
            <Title marginTop="mt-8">Top Revenue Increases</Title>
            <List marginTop="mt-2">
              {data.top_customers.top_customers_by_revenue.map((item) => (
                <ListItem key={item.customer.customer_id}>
                  <Text>{item.customer.customer_name}</Text>
                  <Text>
                    <Bold>{(parseFloat(item.value) * 100).toFixed(2)}</Bold>
                    {"% "}
                  </Text>
                </ListItem>
              ))}
            </List>
          </div>
          <div>
            <Title marginTop="mt-8">Top Revenue Decreases</Title>
            <List marginTop="mt-2">
              {data.top_customers.top_customers_by_revenue.map((item) => (
                <ListItem key={item.customer.customer_id}>
                  <Text>{item.customer.customer_name}</Text>
                  <Text>
                    <Bold>{(parseFloat(item.value) * 100).toFixed(2)}</Bold>
                    {"% "}
                  </Text>
                </ListItem>
              ))}
            </List>
          </div>
        </ColGrid> */}
      </div>
    </div>
  );
};

export default ExperimentDetails;
