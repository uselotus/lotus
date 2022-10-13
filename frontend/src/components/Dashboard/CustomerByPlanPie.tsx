import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom";
import { Pie } from "@ant-design/plots";
import { Paper } from "../base/Paper";
import { Title } from "../base/Typograpy/index.";

export const CustomerByPlanPie = (props: any) => {
  const data = [
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
  const config = {
    legend: {
      position: "bottom" as any,
    },
    appendPadding: 20,
    data,
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
    <Paper>
      <Title level={2}>*Preview* Customer by Plan</Title>
      <div className="h-[390px]">
        <Pie {...config} />
      </div>
    </Paper>
  );
};
