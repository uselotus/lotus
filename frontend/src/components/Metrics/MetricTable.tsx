import React, {FC, useRef, useState} from "react";

import {
  ProTable,
  ProFormInstance,
  ProColumns,
} from "@ant-design/pro-components";
import { Tag } from "antd";
import { MetricType } from "../../types/metric-type";
import MetricDetails from "./MetricDetails";

export const colorMap = new Map<string, string>([
  ["count", "green"],
  ["sum", "blue"],
  ["max", "pink"],
  ["min", "purple"],
  ["latest", "orange"],
  ["average", "cyan"],
  ["unique", "geekblue"],
]);

interface Props {
  metricArray: MetricType[];
}

const MetricTable: FC<Props> = ({ metricArray }) => {
  const formRef = useRef<ProFormInstance>();
  const [currentMetric, setCurrentMetric] = useState<MetricType | null>()

  const columns: ProColumns<MetricType>[] = [
    {
      width: 10,
    },
    {
      title: "Metric Name",
      width: 150,
      dataIndex: "billable_metric_name",
      align: "left",
    },
    {
      title: "Type",
      width: 100,
      dataIndex: "metric_type",
      align: "left",
    },
    {
      title: "Event Name",
      width: 120,
      dataIndex: "event_name",
      align: "left",
    },
    {
      title: "Aggregation Type",
      width: 120,
      dataIndex: "usage_aggregation_type",
      render: (_, record) => (
        <Tag color={colorMap.get(record.usage_aggregation_type)}>
          {record.usage_aggregation_type}
        </Tag>
      ),
    },
    {
      title: "Property Name",
      width: 120,
      dataIndex: "property_name",
      align: "left",
    },
  ];

  return (
    <div className="border-2 border-solid rounded border-[#EAEAEB]">
      <ProTable<MetricType>
        columns={columns}
        dataSource={metricArray}
        onRow={(record, rowIndex) => {
                    return {
                        onClick: event => {
                            console.log(event, "heree")
                            setCurrentMetric(record)
                        }
          };
        }}
        toolBarRender={false}
        rowKey="customer_id"
        formRef={formRef}
        search={false}
        className="w-full"
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
        }}
        options={false}
      />
        {!!currentMetric && <MetricDetails metric={currentMetric} onclose={() => setCurrentMetric(null)} /> }
    </div>
  );
};

export default MetricTable;
