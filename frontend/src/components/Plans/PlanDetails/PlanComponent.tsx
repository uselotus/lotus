// @ts-ignore
import React, { FC } from "react";
import "./PlanDetails.css";
import { Component } from "../../../types/plan-type";

interface PlanComponentsProps {
  components?: Component[];
}

const PlanComponents: FC<PlanComponentsProps> = ({ components }) => {
  const dummy_components = [
    {
      metric: "API calls",
      cost: "$4 / 20 Unit(s)",
      FreeUnits: 10,
      MaxUnits: 10,
    },
    {
      metric: "Unique Languages",
      cost: "$4 / 20 Unit(s)",
      FreeUnits: 10,
      MaxUnits: 10,
    },
    {
      metric: "API calls",
      cost: "$4 / 20 Unit(s)",
      FreeUnits: 10,
      MaxUnits: 10,
    },
  ];

  return (
    <div className="">
      <div className="pb-5 pt-3 font-main font-bold text-[20px]">
        Components:
      </div>
      {components && components.length > 0 ? (
        <div className="flex items-center justify-start flex-wrap">
          {components.map((component) => (
            <div className="pt-2 pb-4 bg-[#FAFAFA] rounded planComponent mr-4 mb-2 px-4">
              <div className="planDetails planComponentMetricName">
                <div className="pr-1">Metric:</div>
                <div> {component.billable_metric.billable_metric_name}</div>
              </div>
              <div className="planDetails">
                <div className="pr-1 planComponentLabel">Cost:</div>
                <div className="planComponentCost">
                  {" $"}
                  {component.cost_per_batch} /{" "}
                  {component.metric_units_per_batch} Unit
                  {component.metric_units_per_batch > 1 ? "s" : null}{" "}
                </div>
              </div>
              <div className="flex items-center">
                <div className="planDetails pr-6">
                  <div className="pr-2 planComponentLabel">Free Units:</div>
                  <div>{component.free_metric_units}</div>
                </div>
                <div className="planDetails">
                  <div className="pr-2 planComponentLabel">Max Units:</div>
                  <div>{component.max_metric_units}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-start flex-wrap">
          No components
        </div>
      )}
    </div>
  );
};
export default PlanComponents;
