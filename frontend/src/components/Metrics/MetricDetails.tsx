import { Modal, Tag } from "antd";
import { MetricType } from "../../types/metric-type";
// @ts-ignore
import React, { FC, Fragment } from "react";
import { colorMap } from "./MetricTable";

interface MetricDetailsProps {
  metric: MetricType;
  onclose: () => void;
}

const metricTypeColorMap = new Map<string, string>([
  ["counter", "green"],
  ["stateful", "blue"],
  ["rate", "purple"],
]);

const eventTypeColorMap = new Map<string, string>([
  ["delta", "green"],
  ["total", "blue"],
]);

const MetricDetails: FC<MetricDetailsProps> = ({ metric, onclose }) => {
  return (
    <Modal
      visible
      title={
        <b>
          {" "}
          {metric?.billable_metric_name
            ? metric.billable_metric_name
            : "Metric"}{" "}
        </b>
      }
      cancelText="Close"
      width={800}
      onCancel={onclose}
      onOk={onclose}
    >
      <div className="py-4 grid grid-cols-2 items-start justify-between  px-8 rounded-lg bg-[#FFFFFF]  border-2 border-solid  border-[#EAEAEB]">
        <p>
          <b className="mr-2">Event Name:</b> {metric.event_name}
        </p>
        <p>
          <b className="mr-2">Cost Metric:</b>{" "}
          {metric.is_cost_metric ? "Yes" : "No"}
        </p>
        <p>
          <b className="mr-2">Property Name:</b> {metric.property_name ?? "N/A"}
        </p>
        <p>
          <b className="mr-2">Metric Type:</b>
          {metric.metric_type === "stateful"
            ? "continuous"
            : metric.metric_type}
        </p>
        <p>
          <b className="mr-2">Per Time Unit:</b>{" "}
          {metric.granularity === "total" ? "none" : metric.granularity}
        </p>

        <p>
          <b className="mr-2">Usage Aggregation Type:</b>
          <Tag color={colorMap.get(metric.usage_aggregation_type)}>
            {metric.usage_aggregation_type}
          </Tag>
        </p>
        {metric.metric_type === "rate" && (
          <p>
            <b className="mr-2">Aggregation Type:</b>
            {!!metric.billable_aggregation_type ? (
              <Tag>{metric.billable_aggregation_type}</Tag>
            ) : (
              "N/A"
            )}
          </p>
        )}
        {metric.metric_type === "stateful" && (
          <p>
            <b className="mr-2">Event Type:</b>
            {!!metric.event_type ? <Tag>{metric.event_type}</Tag> : "N/A"}
          </p>
        )}

        <p>
          <b className="mr-2">Filters:</b>
        </p>
        <div></div>
        <div>
          {metric.numeric_filters?.map((filter, index) => (
            <Tag color="" key={filter.property_name}>
              {<b>{filter.property_name}</b>} {filter.operator} {'"'}
              {filter.comparison_value}
              {'"'}
            </Tag>
          ))}
        </div>
        <div>
          {metric.categorical_filters?.map((filter, index) => (
            <Tag color="" key={filter.property_name}>
              {<b>{filter.property_name}</b>} {filter.operator} {'"'}
              {filter.comparison_value}
              {'"'}
            </Tag>
          ))}
        </div>
      </div>
    </Modal>
  );
};

export default MetricDetails;
