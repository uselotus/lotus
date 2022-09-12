import React, { FC, useState, useEffect } from "react";
import {
  DownOutlined,
  EllipsisOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { Table } from "antd";
import { CustomerTableItem } from "../types/customer-type";
import { Button, Tag, Tooltip } from "antd";
import { PlanDisplay } from "../types/plan-type";
import { useNavigate } from "react-router-dom";
import { MetricType } from "../types/metric-type";

const colorMap = new Map<string, string>([
  ["count", "green"],
  ["sum", "blue"],
  ["max", "pink"],
]);

const columns: ProColumns<MetricType>[] = [
  {
    title: "Event Name",
    width: 120,
    dataIndex: "event_name",
    align: "left",
  },
  {
    title: "Aggregation Type",
    width: 120,
    dataIndex: "aggregation_type",
    render: (_, record) => (
      <Tag color={colorMap.get(record.aggregation_type)}>
        {record.aggregation_type}
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

interface Props {
  metricArray: MetricType[];
}

const MetricTable: FC<Props> = ({ metricArray }) => {
  const navigate = useNavigate();

  const navigateCreateCustomer = () => {
    navigate("/customers/create");
  };
  return (
    <React.Fragment>
      <ProTable<MetricType>
        columns={columns}
        dataSource={metricArray}
        rowKey="customer_id"
        search={false}
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
        }}
        options={false}
      />
    </React.Fragment>
  );
};

export default MetricTable;
