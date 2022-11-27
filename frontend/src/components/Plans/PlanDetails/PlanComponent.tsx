// @ts-ignore
import React, { FC } from "react";
import "./PlanDetails.css";
import { Table } from "antd";
import { Component, Tier } from "../../../types/plan-type";

interface PlanComponentsProps {
  components?: Component[];
}
const renderCost = (record: Tier) => {
  switch (record.type) {
    case "per_unit":
      return (
        <span>
          {"$"}
          {record.cost_per_batch} per {record.metric_units_per_batch} Unit
        </span>
      );

    case "flat":
      return (
        <span>
          {"$"}
          {record.cost_per_batch}{" "}
        </span>
      );

    case "free":
      return <span>{"Free"}</span>;
  }
};

const PlanComponents: FC<PlanComponentsProps> = ({ components }) => {
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
              <div className="">
                <Table
                  dataSource={component.tiers}
                  pagination={false}
                  showHeader={false}
                  bordered={false}
                  rowClassName="bg-[#FAFAFA]"
                  className="bg-background noborderTable"
                  style={{ color: "blue" }}
                  size="middle"
                  columns={[
                    {
                      title: "Range",
                      dataIndex: "range_start",
                      key: "range_start",
                      align: "left",
                      width: "50%",
                      render: (value: any, record: any) => (
                        <span>
                          From {value} to{" "}
                          {record.range_end == null ? "∞" : record.range_end}
                        </span>
                      ),
                    },
                    {
                      title: "Cost",
                      align: "left",
                      dataIndex: "cost_per_batch",
                      key: "cost_per_batch",
                      render: (value: any, record: any) => (
                        <div>{renderCost(record)}</div>
                      ),
                    },
                  ]}
                />
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
