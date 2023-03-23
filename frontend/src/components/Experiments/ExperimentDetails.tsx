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
import { Pie, Line } from "@ant-design/plots";
import { SpecificResults } from "../../types/experiment-type";
import { components } from "../../gen-types";

const arrowURL = new URL("../arrow.svg", import.meta.url).href;

interface Props {
  data: components["schemas"]["AnalysisResults"];
  kpi: string;
}

const ExperimentDetails: FC<Props> = ({ data, kpi }) => {
  const dataFormatterNumber = (number: number) =>
    Math.round((number + Number.EPSILON) * 100) / 100;
  const [revenueLineGraph, setRevenueLineGraph] = React.useState<any>();
  const [revenuePerMetric, setRevenuePerMetric] = React.useState<{
    [planName: string]: { metric_name: string; revenue: number }[];
  }>();

  const [categories, setCategories] = React.useState<string[]>([]);

  function getPlanData(planName: string) {
    if (revenuePerMetric !== undefined) {
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
  }

  useEffect(() => {
    if (data && data.revenue_by_metric_graph !== undefined) {
      console.log(data.revenue_by_metric_graph, 23);
      let newPlans: string[] = [];
      for (let i = 0; i < data.revenue_by_metric_graph.length; i++) {
        newPlans.push(data.revenue_by_metric_graph[i].plan.plan_name);
      }
      setCategories(newPlans);
    }

    if (data && data.revenue_per_day_graph !== undefined) {
      const revenueData: {
        date: string;
        revenue: number;
        plan_name: string;
      }[] = [];
      data.revenue_per_day_graph.forEach((entry) => {
        entry.revenue_per_plan.forEach((plan) => {
          revenueData.push({
            date: entry.date,
            revenue: parseFloat(plan.revenue),
            plan_name: plan.plan.plan_name,
          });
        });
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

  return (
    <div>
      {revenueLineGraph !== undefined && (
        <div className=" bg-[#F9F9F9] px-10 py-10 my-6 ">
          <div className="text-xl text-black font-semiBold">
            Revenue over time
          </div>

          <Line
            data={revenueLineGraph}
            seriesField="plan_name"
            xField="date"
            yField="revenue"
            color={["#C3986B", "#E4D5C5", "#EAECF0", "#065F46", "#171412"]}
            lineStyle={{
              lineWidth: 2,
            }}
            yAxis={{
              grid: {
                line: {
                  style: {
                    stroke: "rgba(0, 0, 0, 0.05)",
                  },
                },
              },
            }}
            xAxis={{
              type: "time",

              label: {
                autoHide: true,
                autoRotate: false,
              },
            }}
            legend={{
              position: "top",
              layout: "horizontal",
              label: {
                style: {
                  fontSize: 30,
                },
              },
            }}
          />
        </div>
      )}

      {revenuePerMetric !== undefined && (
        <div className=" bg-[#F9F9F9] px-10 py-10 my-6 ">
          <div className="text-xl font-semiBold text-black">
            Revenue by metric
          </div>
          <div className="w-full h-[1.5px] my-8 bg-card-divider" />
          <div className="grid grid-cols-2 gap-24">
            {data.revenue_by_metric_graph.map((item) => (
              <div className="col-span-1">
                <div className="text-base  font-semiBold mb-6">
                  {item.plan.plan_name}
                </div>
                <Pie
                  data={getPlanData(item.plan.plan_name)}
                  colorField="metric_name"
                  angleField="revenue"
                  legend={{
                    position: "right",
                    layout: "vertical",
                    label: {
                      style: {
                        fontSize: 30,
                      },
                    },
                  }}
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

      <div className=" bg-[#F9F9F9] px-10 py-10 my-6 ">
        <div className="text-xl  font-semiBold text-black">Top Customers</div>
        <div className="w-full h-[1.5px] my-8 bg-card-divider" />
        <div className="grid grid-cols-4  gap-12 ">
          {data.top_customers_by_plan &&
            data.top_customers_by_plan.map((item) => (
              <div className="col-span-1">
                <div className="text-base  font-semiBold">
                  Total Revenue On:
                </div>
                <div className="text-base  font-semiBold">
                  {item.plan.plan_name}
                </div>
                <List marginTop="mt-4">
                  {item.top_customers_by_revenue.map((item) => (
                    <ListItem key={item.customer.customer_id}>
                      <div className="text-sm  text-card-grey">
                        {item.customer.customer_name}
                      </div>
                      <div className=" text-black">
                        {(parseFloat(item.value) * 100).toFixed(2)}
                        {"% "}
                      </div>
                    </ListItem>
                  ))}
                </List>
              </div>
            ))}
          {data.top_customers_by_plan &&
            data.top_customers_by_plan.map((item) => (
              <div className="col-span-1">
                <div className="text-base  font-semiBold">
                  Average Revenue On:
                </div>
                <div className="text-base  font-semiBold">
                  {item.plan.plan_name}
                </div>
                <List marginTop="mt-4">
                  {item.top_customers_by_average_revenue.map((item) => (
                    <ListItem key={item.customer.customer_id}>
                      <div className="text-sm  text-card-grey">
                        {item.customer.customer_name}
                      </div>{" "}
                      <div className=" text-black">
                        {(parseFloat(item.value) * 100).toFixed(2)}
                        {"% "}
                      </div>
                    </ListItem>
                  ))}
                </List>
              </div>
            ))}
        </div>

        {/* <ColGrid numColsMd={4} gapX="gap-x-8" gapY="gap-y-2">
          <div>
            <Title marginTop="">Revenue on </Title>
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
