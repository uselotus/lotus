/* eslint-disable import/prefer-default-export */
/* eslint-disable react/jsx-props-no-spreading */
import React from "react";
import { Pie } from "@ant-design/plots";
import { useQuery, UseQueryResult } from "react-query";
import { Paper } from "../base/Paper";
import { PlansByCustomer } from "../../api/api";
import LoadingSpinner from "../LoadingSpinner";
import { PlansByCustomerArray } from "../../types/plan-type";

export function CustomerByPlanPie() {
  const { data, isLoading }: UseQueryResult<PlansByCustomerArray> =
    useQuery<PlansByCustomerArray>(["customer_by_plan_pie"], () =>
      PlansByCustomer.getPlansByCustomer().then((res) => res)
    );

  const config = {
    legend: {
      position: "bottom" as const,
    },
    appendPadding: 20,
    data: data?.results as unknown as Record<string, string>[],
    angleField: "num_customers",
    colorField: "plan_name",
    color: ["#33658A", "#547AA5", "#C3986B", "#D9D9D9", "#171412"],
    radius: 1,
    innerRadius: 0.6,
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
      title: false as const,

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
    <Paper className="h-full" border>
      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="">
          <h2>Current Plan Distribution</h2>
          <div className="h-[390px]">
            <Pie {...config} />
          </div>
        </div>
      )}
    </Paper>
  );
}
